from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from models.product import ProductVariant
from utils.cart import add_item, build_display_lines, get_cart_lines, get_totals, remove_item, update_item_qty
from utils.formatting import format_naira
from utils.templates import templates

router = APIRouter()

FREE_SHIPPING_THRESHOLD = Decimal("10000")


def _cart_context(request: Request, db: Session) -> dict:
    lines = get_cart_lines(request, db)
    totals = get_totals(lines)
    lines = build_display_lines(lines)

    item_count = sum(line["qty"] for line in lines)
    qualifies_free_shipping = totals["subtotal"] >= FREE_SHIPPING_THRESHOLD

    return {
        "lines": lines,
        "item_count": item_count,
        "subtotal_display": format_naira(totals["subtotal"]),
        "total_display": format_naira(totals["total"]),
        "qualifies_free_shipping": qualifies_free_shipping,
    }


@router.get("/cart")
async def view_cart(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="cart.html",
        context=_cart_context(request, db),
    )


@router.post("/cart/add")
async def add_to_cart(
    request: Request,
    db: Session = Depends(get_db),
    variant_id: int = Form(...),
    qty: int = Form(1),
):
    variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).one_or_none()
    if variant is not None and variant.stock_qty > 0:
        add_item(request, product_id=variant.product_id, variant_id=variant.id, qty=max(1, qty))
    return RedirectResponse(url="/cart", status_code=303)


@router.post("/cart/update")
async def update_cart_item(
    request: Request,
    variant_id: int = Form(...),
    qty: int = Form(...),
):
    update_item_qty(request, variant_id=variant_id, qty=qty)
    return RedirectResponse(url="/cart", status_code=303)


@router.post("/cart/remove")
async def remove_cart_item(request: Request, variant_id: int = Form(...)):
    remove_item(request, variant_id=variant_id)
    return RedirectResponse(url="/cart", status_code=303)
