from decimal import Decimal


def format_naira(amount) -> str:
    value = Decimal(str(amount))
    if value == value.to_integral_value():
        return f"₦{value:,.0f}"
    return f"₦{value:,.2f}"
