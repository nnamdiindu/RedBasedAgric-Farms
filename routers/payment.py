import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from models.order import Order, OrderItem
from routers.checkout import (
    DELIVERY_METHODS,
    LOCAL_FEE_DISPLAY,
    delivery_fee_at_checkout,
    delivery_fee_display,
    delivery_fee_is_quoted,
)
from utils.cart import build_display_lines, clear_cart, get_cart_lines, get_totals
from utils.delivery_fee import (
    DELIVERY_FEE_REF_MARKER,
    delivery_fee_transaction_reference,
    order_reference_from_fee_reference,
)
from utils.formatting import format_naira
from utils.geo import is_local_request
from utils.mailer import (
    send_delivery_fee_paid_email,
    send_delivery_fee_request_to_admin,
    send_order_confirmation_email,
)
from utils.paystack import initialize_transaction, verify_transaction
from utils.templates import templates

logger = logging.getLogger("redbasedfarm.payment")

router = APIRouter()

PAYMENT_METHODS = {
    "paystack": {
        "label": "Paystack",
        "meta": "Card, bank, transfer, USSD via Paystack checkout",
        "icon": "bi-phone",
    },
    "bank_transfer": {
        "label": "Bank Transfer",
        "meta": "GTBank, Zenith, Access...",
        "icon": "bi-bank",
    },
}


def _generate_reference(db: Session) -> str:
    for _ in range(5):
        reference = f"RBA-{secrets.token_hex(4).upper()}"
        if db.query(Order).filter(Order.reference == reference).one_or_none() is None:
            return reference
    raise RuntimeError("Could not generate a unique order reference")


def _require_checkout_state(request: Request, db: Session):
    """Returns (lines, shipping, delivery_method), or a RedirectResponse if a
    prerequisite step (cart/shipping/delivery) hasn't been completed."""
    lines = get_cart_lines(request, db)
    if not lines:
        return RedirectResponse(url="/cart", status_code=303)

    shipping = request.session.get("shipping")
    if not shipping:
        return RedirectResponse(url="/checkout", status_code=303)

    delivery = request.session.get("delivery")
    if not delivery or delivery.get("method") not in DELIVERY_METHODS:
        return RedirectResponse(url="/delivery", status_code=303)

    return lines, shipping, delivery["method"]


def _payment_context(lines, shipping, delivery_method, is_local, payment_error=None) -> dict:
    delivery_fee = delivery_fee_at_checkout(delivery_method, is_local)
    totals = get_totals(lines, delivery_fee)
    return {
        "payment_methods": PAYMENT_METHODS,
        "lines": build_display_lines(lines),
        "subtotal_display": format_naira(totals["subtotal"]),
        "delivery_fee_display": delivery_fee_display(delivery_method, is_local),
        "total_display": format_naira(totals["total"]),
        "shipping": shipping,
        "payment_error": payment_error,
    }


def _create_pending_order(db: Session, lines, shipping, delivery_method, payment_method, is_local) -> Order:
    delivery_fee = delivery_fee_at_checkout(delivery_method, is_local)
    totals = get_totals(lines, delivery_fee)

    order = Order(
        reference=_generate_reference(db),
        status="pending",
        payment_method=payment_method,
        customer_name=f"{shipping['first_name']} {shipping['last_name']}".strip(),
        customer_email=shipping["email"],
        customer_phone=shipping["phone"],
        shipping_line1=shipping["address1"],
        shipping_line2=shipping.get("address2") or None,
        shipping_city=shipping["city"],
        shipping_state=shipping["state"],
        delivery_method=delivery_method,
        delivery_fee=delivery_fee,
        delivery_fee_status="pending" if delivery_fee_is_quoted(delivery_method, is_local) else None,
        subtotal=totals["subtotal"],
        total=totals["total"],
        currency="NGN",
    )
    for line in lines:
        order.items.append(
            OrderItem(
                product_id=line["product_id"],
                variant_id=line["variant_id"],
                product_name_snapshot=line["product_name"],
                variant_label_snapshot=line["size_label"],
                unit_price_snapshot=line["unit_price"],
                qty=line["qty"],
                line_total=line["line_total"],
            )
        )

    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def _send_confirmation_email(order: Order) -> None:
    try:
        send_order_confirmation_email(order)
    except Exception:
        logger.exception("Failed to send order confirmation email for order %s", order.reference)
    if order.delivery_fee_status == "pending":
        try:
            send_delivery_fee_request_to_admin(order)
        except Exception:
            logger.exception("Failed to send delivery fee request to admin for order %s", order.reference)


def _mark_order_paid(db: Session, order: Order) -> None:
    if order.status == "paid":
        return
    order.status = "paid"
    order.paid_at = datetime.now(timezone.utc)
    db.commit()
    _send_confirmation_email(order)


def _mark_delivery_fee_paid(db: Session, fee_reference: str, amount_kobo: int | None) -> Order | None:
    """Records a successful delivery-fee charge. Returns the order, or None if
    the reference doesn't match one."""
    order_reference = order_reference_from_fee_reference(fee_reference)
    order = db.query(Order).filter(Order.reference == order_reference).one_or_none()
    if order is None or order.delivery_fee_status == "paid":
        return order
    expected_kobo = int(order.delivery_fee * 100)
    if amount_kobo is None or amount_kobo < expected_kobo:
        logger.error(
            "Delivery fee charge %s for order %s was %s kobo, expected %s",
            fee_reference, order.reference, amount_kobo, expected_kobo,
        )
        return order

    order.delivery_fee_status = "paid"
    order.delivery_fee_paid_at = datetime.now(timezone.utc)
    db.commit()
    try:
        send_delivery_fee_paid_email(order)
    except Exception:
        logger.exception("Failed to send delivery fee receipt for order %s", order.reference)
    return order


def _public_base_url(request: Request) -> str:
    return os.getenv("PUBLIC_BASE_URL", str(request.base_url).rstrip("/"))


def _verify_success(reference: str) -> dict | None:
    """Paystack transaction data if the charge succeeded, else None."""
    try:
        result = verify_transaction(reference)
    except httpx.HTTPError:
        logger.exception("Failed to verify Paystack transaction %s", reference)
        return None
    data = result.get("data", {})
    return data if data.get("status") == "success" else None


@router.get("/payment")
async def payment(request: Request, db: Session = Depends(get_db)):
    state = _require_checkout_state(request, db)
    if isinstance(state, RedirectResponse):
        return state
    lines, shipping, delivery_method = state

    return templates.TemplateResponse(
        request=request,
        name="payment.html",
        context=_payment_context(lines, shipping, delivery_method, is_local_request(request)),
    )


@router.post("/payment")
async def submit_payment(request: Request, db: Session = Depends(get_db)):
    state = _require_checkout_state(request, db)
    if isinstance(state, RedirectResponse):
        return state
    lines, shipping, delivery_method = state

    form = await request.form()
    payment_method = form.get("payment_method")
    if payment_method not in PAYMENT_METHODS:
        payment_method = "paystack"

    is_local = is_local_request(request)
    order = _create_pending_order(db, lines, shipping, delivery_method, payment_method, is_local)

    if payment_method in ("bank_transfer", "cod"):
        order.status = "pending_manual"
        db.commit()
        clear_cart(request)
        _send_confirmation_email(order)
        return RedirectResponse(url=f"/order_confirmation?reference={order.reference}", status_code=303)

    callback_url = f"{_public_base_url(request)}/payment/callback"
    amount_kobo = int(order.total * 100)

    try:
        result = initialize_transaction(
            email=order.customer_email,
            amount_kobo=amount_kobo,
            reference=order.reference,
            callback_url=callback_url,
        )
        authorization_url = result.get("data", {}).get("authorization_url")
        if not authorization_url:
            raise ValueError("Paystack response did not include an authorization_url")
    except (httpx.HTTPError, ValueError):
        logger.exception("Failed to initialize Paystack transaction for order %s", order.reference)
        order.status = "failed"
        db.commit()
        return templates.TemplateResponse(
            request=request,
            name="payment.html",
            context=_payment_context(
                lines,
                shipping,
                delivery_method,
                is_local,
                payment_error="We couldn't reach Paystack right now. Please try again.",
            ),
        )

    clear_cart(request)
    return RedirectResponse(url=authorization_url, status_code=303)


@router.get("/payment/callback")
async def payment_callback(request: Request, reference: str, db: Session = Depends(get_db)):
    if DELIVERY_FEE_REF_MARKER in reference:
        order_reference = order_reference_from_fee_reference(reference)
        order = db.query(Order).filter(Order.reference == order_reference).one_or_none()
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.delivery_fee_status != "paid":
            data = _verify_success(reference)
            if data:
                _mark_delivery_fee_paid(db, reference, data.get("amount"))
        return RedirectResponse(url=f"/order_confirmation?reference={order.reference}", status_code=303)

    order = db.query(Order).filter(Order.reference == reference).one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != "paid" and _verify_success(reference):
        _mark_order_paid(db, order)

    return RedirectResponse(url=f"/order_confirmation?reference={order.reference}", status_code=303)


@router.post("/webhook/paystack")
async def paystack_webhook(request: Request, db: Session = Depends(get_db)):
    secret_key = os.getenv("PAYSTACK_SECRET_KEY")
    if not secret_key:
        raise HTTPException(status_code=500, detail="Paystack secret key not configured")

    body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")
    expected_signature = hmac.new(secret_key.encode("utf-8"), body, hashlib.sha512).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(body)

    if payload.get("event") == "charge.success":
        data = payload.get("data", {})
        reference = data.get("reference") or ""
        if DELIVERY_FEE_REF_MARKER in reference:
            _mark_delivery_fee_paid(db, reference, data.get("amount"))
        else:
            order = db.query(Order).filter(Order.reference == reference).one_or_none()
            if order is not None:
                _mark_order_paid(db, order)

    return {"status": "ok"}


@router.get("/order_confirmation")
async def order_confirmation(request: Request, reference: str | None = None, db: Session = Depends(get_db)):
    order = None
    if reference:
        order = db.query(Order).filter(Order.reference == reference).one_or_none()

    if order is None:
        return templates.TemplateResponse(request=request, name="order_confirmation.html", context={})

    delivery_line1 = order.shipping_line1
    if order.shipping_line2:
        delivery_line1 += f", {order.shipping_line2}"

    return templates.TemplateResponse(
        request=request,
        name="order_confirmation.html",
        context={
            "customer_first_name": order.customer_name.split()[0] if order.customer_name else None,
            "order_reference": order.reference,
            "delivery_line1": delivery_line1,
            "delivery_line2": f"{order.shipping_city}, {order.shipping_state}",
            "eta_display": DELIVERY_METHODS.get(order.delivery_method, {}).get("meta"),
            "order_total_display": format_naira(order.total),
            "delivery_fee_status": order.delivery_fee_status,
            "delivery_fee_display": (
                LOCAL_FEE_DISPLAY if order.delivery_fee_status == "pending" else format_naira(order.delivery_fee)
            ),
        },
    )


@router.get("/order/{reference}/delivery-fee")
async def pay_delivery_fee(request: Request, reference: str, db: Session = Depends(get_db)):
    """Link emailed to the customer once the admin has quoted their delivery
    fee. Starts a fresh Paystack charge for just the fee."""
    order = db.query(Order).filter(Order.reference == reference).one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.delivery_fee_status != "quoted":
        # Not quoted yet, already paid, or not a quoted-fee order.
        return RedirectResponse(url=f"/order_confirmation?reference={order.reference}", status_code=303)

    try:
        result = initialize_transaction(
            email=order.customer_email,
            amount_kobo=int(order.delivery_fee * 100),
            reference=delivery_fee_transaction_reference(order.reference),
            callback_url=f"{_public_base_url(request)}/payment/callback",
        )
        authorization_url = result.get("data", {}).get("authorization_url")
        if not authorization_url:
            raise ValueError("Paystack response did not include an authorization_url")
    except (httpx.HTTPError, ValueError):
        logger.exception("Failed to initialize delivery fee transaction for order %s", order.reference)
        raise HTTPException(
            status_code=502,
            detail="We couldn't reach Paystack right now. Please try the link again shortly.",
        )

    return RedirectResponse(url=authorization_url, status_code=303)
