import os
import smtplib
from email.message import EmailMessage

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
