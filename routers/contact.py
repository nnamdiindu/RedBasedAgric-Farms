import logging

from fastapi import APIRouter, Request

from utils.mailer import send_contact_email
from utils.templates import templates

logger = logging.getLogger("redbasedfarm.contact")

router = APIRouter()


@router.get("/contact")
async def contact_us(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="contact.html",
        context={"contact_values": {}}
    )


@router.post("/contact")
async def submit_contact_form(request: Request):
    form = await request.form()

    contact_values = {
        "name": (form.get("name") or "").strip(),
        "email": (form.get("email") or "").strip(),
        "subject": (form.get("subject") or "").strip(),
        "message": (form.get("message") or "").strip(),
    }

    contact_status = "success"
    contact_error = None

    if not all(contact_values.values()):
        contact_status = "error"
        contact_error = "Please fill in all fields before sending your message."
    else:
        try:
            send_contact_email(
                contact_values["name"],
                contact_values["email"],
                contact_values["subject"],
                contact_values["message"],
            )
            contact_values = {}
        except Exception:
            logger.exception("Failed to send contact form email")
            contact_status = "error"
            contact_error = "We couldn't send your message right now. Please try again later or reach us directly by phone or email."

    return templates.TemplateResponse(
        request=request,
        name="contact.html",
        context={
            "contact_status": contact_status,
            "contact_error": contact_error,
            "contact_values": contact_values,
        }
    )
