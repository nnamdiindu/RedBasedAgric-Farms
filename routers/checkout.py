import re
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from utils.cart import build_display_lines, get_cart_lines, get_totals
from utils.formatting import format_naira
from utils.nigeria_states import NIGERIA_STATES
from utils.templates import templates

router = APIRouter()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

REQUIRED_SHIPPING_FIELDS = [
    "first_name",
    "last_name",
    "email",
    "phone",
    "address1",
    "city",
    "state",
]

DELIVERY_METHODS = {
    "standard": {
        "label": "Standard Delivery",
        "fee": Decimal("0"),
        "fee_display": "Free",
        "badge": "Free shipping!",
        "badge_class": "badge-accent",
        "meta": "2–4 business days. All 36 states",
        "icon": "bi-truck",
    },
    "express": {
        "label": "Express Delivery",
        "fee": Decimal("3500"),
        "fee_display": format_naira(Decimal("3500")),
        "badge": "Fastest",
        "badge_class": "badge-neutral",
        "meta": "Next day. Lagos, Abuja, PH",
        "icon": "bi-bicycle",
    },
    "pickup": {
        "label": "Farm Pickup",
        "fee": Decimal("0"),
        "fee_display": "Free",
        "badge": "No delivery fee",
        "badge_class": "badge-neutral",
        "meta": "Collect from Makurdi depot",
        "icon": "bi-box-seam",
    },
}


def _cart_summary(request: Request, db: Session, delivery_fee: Decimal = Decimal("0")) -> dict:
    lines = get_cart_lines(request, db)
    totals = get_totals(lines, delivery_fee)
    return {
        "lines": build_display_lines(lines),
        "subtotal_display": format_naira(totals["subtotal"]),
        "total_display": format_naira(totals["total"]),
        "has_delivery_fee": delivery_fee > 0,
        "delivery_fee_display": format_naira(delivery_fee) if delivery_fee > 0 else "Free",
    }


def _validate_shipping(form) -> tuple[dict, dict]:
    values = {
        "first_name": (form.get("first_name") or "").strip(),
        "last_name": (form.get("last_name") or "").strip(),
        "email": (form.get("email") or "").strip(),
        "phone": (form.get("phone") or "").strip(),
        "address1": (form.get("address1") or "").strip(),
        "address2": (form.get("address2") or "").strip(),
        "city": (form.get("city") or "").strip(),
        "state": (form.get("state") or "").strip(),
    }
    errors = {}
    for field in REQUIRED_SHIPPING_FIELDS:
        if not values[field]:
            errors[field] = "This field is required."
    if values["email"] and not EMAIL_RE.match(values["email"]):
        errors["email"] = "Enter a valid email address."
    if values["state"] and values["state"] not in NIGERIA_STATES:
        errors["state"] = "Select a valid state."
    return values, errors


@router.get("/checkout")
async def checkout(request: Request, db: Session = Depends(get_db)):
    lines = get_cart_lines(request, db)
    if not lines:
        return RedirectResponse(url="/cart", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="checkout.html",
        context={
            **_cart_summary(request, db),
            "states": NIGERIA_STATES,
            "shipping_values": request.session.get("shipping", {}),
            "shipping_errors": {},
        },
    )


@router.post("/checkout")
async def submit_checkout(request: Request, db: Session = Depends(get_db)):
    lines = get_cart_lines(request, db)
    if not lines:
        return RedirectResponse(url="/cart", status_code=303)

    form = await request.form()
    values, errors = _validate_shipping(form)

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="checkout.html",
            context={
                **_cart_summary(request, db),
                "states": NIGERIA_STATES,
                "shipping_values": values,
                "shipping_errors": errors,
            },
        )

    request.session["shipping"] = values
    return RedirectResponse(url="/delivery", status_code=303)


@router.get("/delivery")
async def delivery(request: Request, db: Session = Depends(get_db)):
    lines = get_cart_lines(request, db)
    if not lines:
        return RedirectResponse(url="/cart", status_code=303)
    shipping = request.session.get("shipping")
    if not shipping:
        return RedirectResponse(url="/checkout", status_code=303)

    selected_method = request.session.get("delivery", {}).get("method", "standard")
    if selected_method not in DELIVERY_METHODS:
        selected_method = "standard"

    return templates.TemplateResponse(
        request=request,
        name="delivery.html",
        context={
            **_cart_summary(request, db, DELIVERY_METHODS[selected_method]["fee"]),
            "delivery_methods": DELIVERY_METHODS,
            "selected_method": selected_method,
            "shipping": shipping,
        },
    )


@router.post("/delivery")
async def submit_delivery(request: Request, db: Session = Depends(get_db)):
    lines = get_cart_lines(request, db)
    if not lines:
        return RedirectResponse(url="/cart", status_code=303)
    if not request.session.get("shipping"):
        return RedirectResponse(url="/checkout", status_code=303)

    form = await request.form()
    method = form.get("delivery_method")
    if method not in DELIVERY_METHODS:
        method = "standard"

    request.session["delivery"] = {"method": method}
    return RedirectResponse(url="/payment", status_code=303)
