import os

from fastapi import Request

LOCAL_COUNTRY = "NG"


def get_request_country(request: Request) -> str | None:
    """Two-letter country code of the visitor. Vercel sets x-vercel-ip-country
    from the client IP; locally there's no such header, so DEV_COUNTRY can
    stand in for it (e.g. DEV_COUNTRY=NG)."""
    country = request.headers.get("x-vercel-ip-country") or os.getenv("DEV_COUNTRY")
    return country.upper() if country else None


def is_local_request(request: Request) -> bool:
    # No country at all (e.g. running locally without DEV_COUNTRY) counts as
    # local: this is a Nigerian shop, and on Vercel the header is always set.
    country = get_request_country(request)
    return country is None or country == LOCAL_COUNTRY
