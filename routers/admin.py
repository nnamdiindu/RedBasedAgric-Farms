import hmac
import logging
import os
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from models.order import Order
from routers.checkout import DELIVERY_METHODS
from utils.delivery_fee import quote_delivery_fee
from utils.formatting import format_naira
from utils.templates import templates

logger = logging.getLogger("redbasedfarm.admin")

router = APIRouter(prefix="/admin")

ADMIN_SESSION_KEY = "is_admin"

# Recently completed (fee paid) orders shown beneath the work queue.
RECENT_PAID_LIMIT = 20


def _is_admin(request: Request) -> bool:
    return request.session.get(ADMIN_SESSION_KEY) is True


def _login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/admin/login", status_code=303)


def _flash(request: Request, kind: str, message: str) -> None:
    request.session["admin_flash"] = {"kind": kind, "message": message}


def _order_row(order: Order) -> dict:
    address = order.shipping_line1
    if order.shipping_line2:
        address += f", {order.shipping_line2}"
    return {
        "reference": order.reference,
        "status": order.status,
        "is_goods_paid": order.status == "paid",
        "payment_method": order.payment_method,
        "delivery_fee_status": order.delivery_fee_status,
        "delivery_method_label": DELIVERY_METHODS.get(order.delivery_method, {}).get("label", order.delivery_method),
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "customer_email": order.customer_email,
        "address": address,
        "city_state": f"{order.shipping_city}, {order.shipping_state}",
        "item_lines": [
            f"{item.product_name_snapshot} ({item.variant_label_snapshot}) x{item.qty}"
            for item in order.items
        ],
        "subtotal_display": format_naira(order.subtotal),
        "delivery_fee_input": f"{Decimal(order.delivery_fee or 0).normalize():f}",
        "delivery_fee_display": format_naira(order.delivery_fee),
        "total_display": format_naira(order.total),
        "created_at": order.created_at.strftime("%d %b %Y, %H:%M") if order.created_at else "",
    }


@router.get("/login")
async def login(request: Request):
    if _is_admin(request):
        return RedirectResponse(url="/admin/orders", status_code=303)
    return templates.TemplateResponse(request=request, name="admin_login.html", context={"error": None})


@router.post("/login")
async def submit_login(request: Request, password: str = Form("")):
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_password:
        logger.error("ADMIN_PASSWORD is not set; admin login is disabled")
        error = "Admin login isn't configured yet."
    elif hmac.compare_digest(password.encode("utf-8"), admin_password.encode("utf-8")):
        request.session[ADMIN_SESSION_KEY] = True
        return RedirectResponse(url="/admin/orders", status_code=303)
    else:
        error = "Incorrect password."

    return templates.TemplateResponse(
        request=request, name="admin_login.html", context={"error": error}, status_code=401
    )


@router.post("/logout")
async def logout(request: Request):
    request.session.pop(ADMIN_SESSION_KEY, None)
    return _login_redirect()


@router.get("")
async def admin_home(request: Request):
    return RedirectResponse(url="/admin/orders", status_code=303)


@router.get("/orders")
async def orders(request: Request, db: Session = Depends(get_db)):
    if not _is_admin(request):
        return _login_redirect()

    awaiting = (
        db.query(Order)
        .filter(Order.delivery_fee_status.in_(["pending", "quoted"]))
        .order_by(Order.created_at)
        .all()
    )
    recent_paid = (
        db.query(Order)
        .filter(Order.delivery_fee_status == "paid")
        .order_by(Order.delivery_fee_paid_at.desc())
        .limit(RECENT_PAID_LIMIT)
        .all()
    )
    rows = [_order_row(order) for order in awaiting]

    return templates.TemplateResponse(
        request=request,
        name="admin_orders.html",
        context={
            "needs_fee": [row for row in rows if row["delivery_fee_status"] == "pending"],
            "awaiting_payment": [row for row in rows if row["delivery_fee_status"] == "quoted"],
            "recent_paid": [_order_row(order) for order in recent_paid],
            "flash": request.session.pop("admin_flash", None),
        },
    )


@router.post("/orders/{reference}/delivery-fee")
async def set_delivery_fee(
    request: Request,
    reference: str,
    fee: str = Form(""),
    db: Session = Depends(get_db),
):
    if not _is_admin(request):
        return _login_redirect()

    order = db.query(Order).filter(Order.reference == reference).one_or_none()
    if order is None:
        _flash(request, "error", f"Order {reference} not found.")
        return RedirectResponse(url="/admin/orders", status_code=303)

    try:
        fee_amount = Decimal(fee.replace(",", "").replace("₦", "").strip())
        if not fee_amount.is_finite():
            raise InvalidOperation
    except InvalidOperation:
        _flash(request, "error", f"{reference}: enter the fee as a number, e.g. 2500.")
        return RedirectResponse(url="/admin/orders", status_code=303)

    try:
        quote_delivery_fee(db, order, fee_amount)
    except ValueError as error:
        _flash(request, "error", f"{reference}: {error}")
        return RedirectResponse(url="/admin/orders", status_code=303)
    except Exception:
        # The fee is saved before emailing, so a failed email can be retried
        # by submitting the fee again.
        logger.exception("Failed to send delivery fee quote for order %s", reference)
        _flash(
            request,
            "error",
            f"{reference}: fee saved as {format_naira(fee_amount)}, but the email to the customer "
            f"failed to send. Submit the fee again to retry.",
        )
        return RedirectResponse(url="/admin/orders", status_code=303)

    _flash(
        request,
        "success",
        f"{reference}: delivery fee {format_naira(fee_amount)} sent to {order.customer_email}.",
    )
    return RedirectResponse(url="/admin/orders", status_code=303)
