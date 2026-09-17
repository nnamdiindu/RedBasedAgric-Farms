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
from routers.checkout import DELIVERY_METHODS
from utils.cart import build_display_lines, clear_cart, get_cart_lines, get_totals
from utils.formatting import format_naira
from utils.mailer import send_order_confirmation_email
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


def _payment_context(lines, shipping, delivery_method, payment_error=None) -> dict:
    delivery_fee = DELIVERY_METHODS[delivery_method]["fee"]
    totals = get_totals(lines, delivery_fee)
    return {
        "payment_methods": PAYMENT_METHODS,
        "lines": build_display_lines(lines),
        "subtotal_display": format_naira(totals["subtotal"]),
        "delivery_fee_display": format_naira(delivery_fee) if delivery_fee > 0 else "Free",
        "total_display": format_naira(totals["total"]),
        "shipping": shipping,
        "payment_error": payment_error,
    }


def _create_pending_order(db: Session, lines, shipping, delivery_method, payment_method) -> Order:
    delivery_fee = DELIVERY_METHODS[delivery_method]["fee"]
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


@router.get("/payment")
async def payment(request: Request, db: Session = Depends(get_db)):
    state = _require_checkout_state(request, db)
    if isinstance(state, RedirectResponse):
        return state
    lines, shipping, delivery_method = state

    return templates.TemplateResponse(
        request=request,
        name="payment.html",
        context=_payment_context(lines, shipping, delivery_method),
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

    order = _create_pending_order(db, lines, shipping, delivery_method, payment_method)

    if payment_method in ("bank_transfer", "cod"):
        order.status = "pending_manual"
        db.commit()
        clear_cart(request)
        _send_confirmation_email(order)
        return RedirectResponse(url=f"/order_confirmation?reference={order.reference}", status_code=303)

    public_base_url = os.getenv("PUBLIC_BASE_URL", str(request.base_url).rstrip("/"))
    callback_url = f"{public_base_url}/payment/callback"
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
                payment_error="We couldn't reach Paystack right now. Please try again.",
            ),
        )

    clear_cart(request)
    return RedirectResponse(url=authorization_url, status_code=303)


@router.get("/payment/callback")
async def payment_callback(request: Request, reference: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.reference == reference).one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != "paid":
        try:
            result = verify_transaction(reference)
        except httpx.HTTPError:
            logger.exception("Failed to verify Paystack transaction %s", reference)
            result = None

        if result and result.get("data", {}).get("status") == "success":
            order.status = "paid"
            order.paid_at = datetime.now(timezone.utc)
            db.commit()
            _send_confirmation_email(order)

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
        reference = payload.get("data", {}).get("reference")
        order = db.query(Order).filter(Order.reference == reference).one_or_none()
        if order is not None and order.status != "paid":
            order.status = "paid"
            order.paid_at = datetime.now(timezone.utc)
            db.commit()
            _send_confirmation_email(order)

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
        },
    )
