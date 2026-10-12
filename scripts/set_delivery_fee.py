# Stopgap admin tool until there's an admin page: sets the delivery fee for a
# local order and emails the customer a Paystack link to pay it. Needs the same
# env as the app (DATABASE_URL, SMTP_*, PUBLIC_BASE_URL). Run with:
#   python scripts/set_delivery_fee.py                  # list orders awaiting a fee
#   python scripts/set_delivery_fee.py RBA-1A2B3C4D 2500
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from database import SessionLocal, init_db
from models.order import Order
from utils.delivery_fee import quote_delivery_fee
from utils.formatting import format_naira


def list_awaiting(db) -> None:
    orders = (
        db.query(Order)
        .filter(Order.delivery_fee_status.in_(["pending", "quoted"]))
        .order_by(Order.created_at)
        .all()
    )
    if not orders:
        print("No orders awaiting a delivery fee.")
        return
    for order in orders:
        fee = format_naira(order.delivery_fee) if order.delivery_fee_status == "quoted" else "-"
        print(
            f"{order.reference}  [{order.status}/{order.delivery_fee_status}]  fee {fee}  "
            f"{order.customer_name}, {order.customer_phone}  "
            f"{order.shipping_line1}, {order.shipping_city}, {order.shipping_state}"
        )


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        if len(sys.argv) == 1:
            list_awaiting(db)
            return
        if len(sys.argv) != 3:
            sys.exit("Usage: python scripts/set_delivery_fee.py [ORDER_REFERENCE FEE]")

        reference, fee_arg = sys.argv[1], sys.argv[2]
        try:
            fee = Decimal(fee_arg.replace(",", ""))
        except InvalidOperation:
            sys.exit(f"Invalid fee: {fee_arg}")

        order = db.query(Order).filter(Order.reference == reference).one_or_none()
        if order is None:
            sys.exit(f"No order with reference {reference}")
        if order.status != "paid":
            print(f"Warning: order {reference} is '{order.status}', not 'paid' - goods payment not confirmed yet.")

        try:
            quote_delivery_fee(db, order, fee)
        except ValueError as error:
            sys.exit(str(error))
        print(f"Delivery fee {format_naira(fee)} set for {reference}; payment link emailed to {order.customer_email}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
