import os

import httpx

PAYSTACK_BASE_URL = "https://api.paystack.co"


def _headers() -> dict:
    secret_key = os.getenv("PAYSTACK_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("PAYSTACK_SECRET_KEY environment variable must be set")
    return {"Authorization": f"Bearer {secret_key}"}


def initialize_transaction(email: str, amount_kobo: int, reference: str, callback_url: str) -> dict:
    response = httpx.post(
        f"{PAYSTACK_BASE_URL}/transaction/initialize",
        headers=_headers(),
        json={
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
            "callback_url": callback_url,
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def verify_transaction(reference: str) -> dict:
    response = httpx.get(
        f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
        headers=_headers(),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()
