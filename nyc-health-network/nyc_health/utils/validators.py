"""Input validators. Each returns the normalised value or raises ValidationError."""
import re
from datetime import date

from nyc_health import config
from nyc_health.exceptions import ValidationError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def require_text(value: str, field: str, max_len: int = 80) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValidationError(f"{field} is required")
    if len(cleaned) > max_len:
        raise ValidationError(f"{field} must be at most {max_len} characters")
    return cleaned


def validate_phone(raw: str) -> str:
    """Accepts NYC numbers in common formats; returns E.164 (+1XXXXXXXXXX)."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValidationError("phone must contain 10 digits")
    if digits[:3] not in config.NYC_AREA_CODES:
        raise ValidationError(f"area code {digits[:3]} is not a NYC area code")
    return f"+1{digits}"


def validate_email(raw: str) -> str:
    cleaned = (raw or "").strip().lower()
    if not _EMAIL_RE.match(cleaned):
        raise ValidationError("email is not valid")
    return cleaned


def validate_birth_date(value: date, today: date) -> date:
    if value > today:
        raise ValidationError("date of birth cannot be in the future")
    if (today - value).days > 120 * 366:
        raise ValidationError("date of birth is implausibly old")
    return value
