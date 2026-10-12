import os
import smtplib
from email.message import EmailMessage

from utils.formatting import format_naira

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
CONTACT_RECIPIENT = os.getenv("CONTACT_RECIPIENT", SMTP_USERNAME)

CONTACT_SUBJECT_LABELS = {
    "order": "Order inquiry",
    "bulk": "Bulk / wholesale purchase",
    "support": "Customer support",
    "partnership": "Partnership",
    "other": "Other",
}


def send_contact_email(full_name: str, email: str, subject: str, message: str) -> None:
    subject_label = CONTACT_SUBJECT_LABELS.get(subject, subject or "General inquiry")

    email_message = EmailMessage()
    email_message["Subject"] = f"[Contact Form] {subject_label} - {full_name}"
    email_message["From"] = SMTP_USERNAME
    email_message["To"] = CONTACT_RECIPIENT
    email_message["Reply-To"] = email
    email_message.set_content(
        f"New contact form submission\n\n"
        f"Name: {full_name}\n"
        f"Email: {email}\n"
        f"Subject: {subject_label}\n\n"
        f"Message:\n{message}\n"
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(email_message)


def _send(email_message: EmailMessage) -> None:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(email_message)


def _address_text(order) -> str:
    address = order.shipping_line1
    if order.shipping_line2:
        address += f", {order.shipping_line2}"
    return address + f"\n{order.shipping_city}, {order.shipping_state}"


def send_order_confirmation_email(order) -> None:
    items_text = "\n".join(
        f"- {item.product_name_snapshot} ({item.variant_label_snapshot}) x{item.qty}: "
        f"{format_naira(item.line_total)}"
        for item in order.items
    )

    if order.delivery_fee_status == "pending":
        delivery_text = "To be confirmed (delivery fee pending)"
        total_label = "Total paid"
        fee_note = (
            "Your delivery fee is pending. We'll work out the cost of delivering to your "
            "location and email you the amount with a link to pay it. Your order will be "
            "dispatched once the delivery fee is paid.\n\n"
        )
    else:
        delivery_text = format_naira(order.delivery_fee) if order.delivery_fee else "Free"
        total_label = "Total"
        fee_note = ""

    email_message = EmailMessage()
    email_message["Subject"] = f"Order Confirmation - {order.reference}"
    email_message["From"] = SMTP_USERNAME
    email_message["To"] = order.customer_email
    email_message.set_content(
        f"Thank you for your order, {order.customer_name}!\n\n"
        f"We've received your order.\n\n"
        f"Order Reference: {order.reference}\n\n"
        f"Items:\n{items_text}\n\n"
        f"Subtotal: {format_naira(order.subtotal)}\n"
        f"Delivery: {delivery_text}\n"
        f"{total_label}: {format_naira(order.total)}\n\n"
        f"{fee_note}"
        f"Delivery Address:\n{_address_text(order)}\n"
    )
    _send(email_message)


def send_delivery_fee_request_to_admin(order) -> None:
    """Tells the farm a local order needs a delivery fee worked out."""
    email_message = EmailMessage()
    email_message["Subject"] = f"[Delivery fee needed] Order {order.reference} - {order.shipping_city}, {order.shipping_state}"
    email_message["From"] = SMTP_USERNAME
    email_message["To"] = CONTACT_RECIPIENT
    email_message["Reply-To"] = order.customer_email
    email_message.set_content(
        f"Order {order.reference} has been paid for and needs a delivery fee.\n\n"
        f"Customer: {order.customer_name}\n"
        f"Phone: {order.customer_phone}\n"
        f"Email: {order.customer_email}\n\n"
        f"Deliver to:\n{_address_text(order)}\n\n"
        f"Goods paid: {format_naira(order.subtotal)}\n"
    )
    _send(email_message)


def send_delivery_fee_quote_email(order, payment_url: str) -> None:
    email_message = EmailMessage()
    email_message["Subject"] = f"Delivery fee for your order {order.reference}"
    email_message["From"] = SMTP_USERNAME
    email_message["To"] = order.customer_email
    email_message.set_content(
        f"Hello {order.customer_name},\n\n"
        f"The delivery fee for order {order.reference} to the address below is "
        f"{format_naira(order.delivery_fee)}.\n\n"
        f"Deliver to:\n{_address_text(order)}\n\n"
        f"Pay the delivery fee securely with Paystack here:\n{payment_url}\n\n"
        f"We'll dispatch your order as soon as the delivery fee is paid.\n"
    )
    _send(email_message)


def send_delivery_fee_paid_email(order) -> None:
    email_message = EmailMessage()
    email_message["Subject"] = f"Delivery fee received - {order.reference}"
    email_message["From"] = SMTP_USERNAME
    email_message["To"] = order.customer_email
    email_message["Bcc"] = CONTACT_RECIPIENT
    email_message.set_content(
        f"Hello {order.customer_name},\n\n"
        f"We've received your delivery fee of {format_naira(order.delivery_fee)} for "
        f"order {order.reference}. Your order is now being prepared for delivery.\n\n"
        f"Order total: {format_naira(order.total)}\n\n"
        f"Deliver to:\n{_address_text(order)}\n"
    )
    _send(email_message)
