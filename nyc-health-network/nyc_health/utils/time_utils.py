"""Time helpers. All datetimes are naive and represent America/New_York local time."""
from datetime import date, datetime, timedelta
from typing import List

from nyc_health import config


def intervals_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """True if interval A and interval B share any time. Touching endpoints do not overlap."""
    return a_start <= b_start < a_end or a_start < b_end <= a_end


def minutes_between(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


def is_slot_aligned(moment: datetime) -> bool:
    return moment.second == 0 and moment.microsecond == 0 and moment.minute % config.APPOINTMENT_SLOT_MINUTES == 0


def within_business_hours(start: datetime, end: datetime) -> bool:
    if start.date() != end.date():
        return False
    return start.hour >= config.BUSINESS_OPEN_HOUR and (
        end.hour < config.BUSINESS_CLOSE_HOUR
        or (end.hour == config.BUSINESS_CLOSE_HOUR and end.minute == 0)
    )


def day_bounds(day: date) -> tuple:
    start = datetime(day.year, day.month, day.day)
    return start, start + timedelta(days=1)


def generate_slots(day: date, duration_minutes: int) -> List[datetime]:
    """All aligned start times on `day` whose appointment would finish inside business hours."""
    slots: List[datetime] = []
    cursor = datetime(day.year, day.month, day.day, config.BUSINESS_OPEN_HOUR)
    close = datetime(day.year, day.month, day.day, config.BUSINESS_CLOSE_HOUR)
    step = timedelta(minutes=config.APPOINTMENT_SLOT_MINUTES)
    length = timedelta(minutes=duration_minutes)
    while cursor + length <= close:
        slots.append(cursor)
        cursor += step
    return slots
