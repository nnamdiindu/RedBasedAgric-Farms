import os
import secrets
from decimal import Decimal

from sqlalchemy.orm import Session

from models.order import Order
from utils.mailer import send_delivery_fee_quote_email

# Delivery-fee charges get their own Paystack reference (Paystack references
# must be unique), shaped "<order reference>-DF-<random>" so the callback and
# webhook can find the order they belong to.
DELIVERY_FEE_REF_MARKER = "-DF-"


def delivery_fee_transaction_reference(order_reference: str) -> str:
    return f"{order_reference}{DELIVERY_FEE_REF_MARKER}{secrets.token_hex(3).upper()}"


def order_reference_from_fee_reference(fee_reference: str) -> str:
    return fee_reference.split(DELIVERY_FEE_REF_MARKER, 1)[0]


def delivery_fee_payment_url(order: Order) -> str:
    base_url = os.getenv("PUBLIC_BASE_URL")
    if not base_url:
        raise RuntimeError("PUBLIC_BASE_URL environment variable must be set to email payment links")
    return f"{base_url.rstrip('/')}/order/{order.reference}/delivery-fee"


def quote_delivery_fee(db: Session, order: Order, fee: Decimal) -> None:
    """Admin action: set the delivery fee for a local order and email the
    customer a link to pay it. Can be re-run to correct a quote until the fee
    is paid."""
    if order.delivery_fee_status not in ("pending", "quoted"):
        raise ValueError(f"Order {order.reference} isn't awaiting a delivery fee quote")
    if fee <= 0:
        raise ValueError("Delivery fee must be greater than zero")

    order.delivery_fee = fee
    order.total = order.subtotal + fee
    order.delivery_fee_status = "quoted"
    db.commit()
    send_delivery_fee_quote_email(order, delivery_fee_payment_url(order))
