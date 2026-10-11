"""Integer-cent money helpers. Never use floats for currency."""


def percent_of(amount_cents: int, pct: int) -> int:
    """`pct` percent of `amount_cents`, rounded half up to the nearest cent."""
    if amount_cents < 0:
        raise ValueError("amount_cents must be non-negative")
    if not 0 <= pct <= 100:
        raise ValueError("pct must be between 0 and 100")
    return (amount_cents * pct + 50) // 100


def format_cents(amount_cents: int) -> str:
    sign = "-" if amount_cents < 0 else ""
    dollars, cents = divmod(abs(amount_cents), 100)
    return f"{sign}${dollars:,}.{cents:02d}"
