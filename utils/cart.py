from decimal import Decimal

from fastapi import Request
from sqlalchemy.orm import Session

from models.product import ProductVariant
from utils.formatting import format_naira

CART_SESSION_KEY = "cart"


def get_cart(request: Request) -> list[dict]:
    return request.session.setdefault(CART_SESSION_KEY, [])


def _find_line(cart: list[dict], variant_id: int) -> dict | None:
    for line in cart:
        if line["variant_id"] == variant_id:
            return line
    return None


def add_item(request: Request, product_id: int, variant_id: int, qty: int = 1) -> None:
    cart = get_cart(request)
    line = _find_line(cart, variant_id)
    if line:
        line["qty"] += qty
    else:
        cart.append({"product_id": product_id, "variant_id": variant_id, "qty": qty})
    request.session[CART_SESSION_KEY] = cart


def update_item_qty(request: Request, variant_id: int, qty: int) -> None:
    cart = get_cart(request)
    if qty <= 0:
        cart = [line for line in cart if line["variant_id"] != variant_id]
    else:
        line = _find_line(cart, variant_id)
        if line:
            line["qty"] = qty
    request.session[CART_SESSION_KEY] = cart


def remove_item(request: Request, variant_id: int) -> None:
    cart = get_cart(request)
    cart = [line for line in cart if line["variant_id"] != variant_id]
    request.session[CART_SESSION_KEY] = cart


def clear_cart(request: Request) -> None:
    request.session[CART_SESSION_KEY] = []


def get_cart_lines(request: Request, db: Session) -> list[dict]:
    """Join session cart entries against current DB state. Prices/names always
    come from the DB, never the cookie. Dead or out-of-stock lines are dropped
    and quantities are clamped to available stock; the session is rewritten
    when that happens so a stale cookie can't linger."""
    cart = get_cart(request)
    lines = []
    changed = False

    for entry in cart:
        variant = (
            db.query(ProductVariant)
            .filter(ProductVariant.id == entry["variant_id"])
            .one_or_none()
        )
        if variant is None or variant.stock_qty <= 0:
            changed = True
            continue

        qty = min(entry["qty"], variant.stock_qty)
        if qty != entry["qty"]:
            changed = True

        product = variant.product
        line_total = variant.price * qty
        lines.append({
            "product_id": product.id,
            "variant_id": variant.id,
            "product_slug": product.slug,
            "product_name": product.name,
            "category": product.category,
            "size_label": variant.size_label,
            "image": product.image_primary,
            "unit_price": variant.price,
            "qty": qty,
            "line_total": line_total,
        })

    if changed:
        request.session[CART_SESSION_KEY] = [
            {
                "product_id": line["product_id"],
                "variant_id": line["variant_id"],
                "qty": line["qty"],
            }
            for line in lines
        ]

    return lines


def get_totals(lines: list[dict], delivery_fee: Decimal = Decimal("0")) -> dict:
    subtotal = sum((line["line_total"] for line in lines), Decimal("0"))
    return {
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total": subtotal + delivery_fee,
    }


def build_display_lines(lines: list[dict]) -> list[dict]:
    return [
        {
            **line,
            "unit_price_display": format_naira(line["unit_price"]),
            "line_total_display": format_naira(line["line_total"]),
        }
        for line in lines
    ]
