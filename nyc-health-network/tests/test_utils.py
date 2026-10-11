from datetime import date, datetime

import pytest

from nyc_health.exceptions import ValidationError
from nyc_health.utils import time_utils, validators
from nyc_health.utils.ids import IdGenerator
from nyc_health.utils.money import format_cents, percent_of


def dt(h, m=0):
    return datetime(2026, 3, 3, h, m)


class TestIntervalsOverlap:
    def test_partial_overlap_at_start(self):
        assert time_utils.intervals_overlap(dt(9), dt(10), dt(8, 30), dt(9, 30))

    def test_partial_overlap_at_end(self):
        assert time_utils.intervals_overlap(dt(9), dt(10), dt(9, 30), dt(10, 30))

    def test_identical_intervals_overlap(self):
        assert time_utils.intervals_overlap(dt(9), dt(10), dt(9), dt(10))

    def test_back_to_back_does_not_overlap(self):
        assert not time_utils.intervals_overlap(dt(9), dt(10), dt(10), dt(11))
        assert not time_utils.intervals_overlap(dt(10), dt(11), dt(9), dt(10))

    def test_disjoint_intervals(self):
        assert not time_utils.intervals_overlap(dt(9), dt(10), dt(13), dt(14))


class TestTimeHelpers:
    def test_slot_alignment(self):
        assert time_utils.is_slot_aligned(dt(9, 30))
        assert not time_utils.is_slot_aligned(dt(9, 15))

    def test_business_hours(self):
        assert time_utils.within_business_hours(dt(8), dt(8, 30))
        assert time_utils.within_business_hours(dt(17, 30), dt(18))
        assert not time_utils.within_business_hours(dt(17, 30), dt(18, 30))
        assert not time_utils.within_business_hours(dt(7, 30), dt(8))

    def test_generate_slots_respects_duration(self):
        slots = time_utils.generate_slots(date(2026, 3, 3), 60)
        assert slots[0] == dt(8)
        assert slots[-1] == dt(17)
        assert len(slots) == 19

    def test_minutes_between(self):
        assert time_utils.minutes_between(dt(9), dt(10, 15)) == 75


class TestValidators:
    @pytest.mark.parametrize("raw", ["(718) 555-0142", "718-555-0142", "+1 718 555 0142", "7185550142"])
    def test_phone_formats_normalize(self, raw):
        assert validators.validate_phone(raw) == "+17185550142"

    def test_phone_rejects_non_nyc_area_code(self):
        with pytest.raises(ValidationError):
            validators.validate_phone("415-555-0100")

    def test_phone_rejects_short_numbers(self):
        with pytest.raises(ValidationError):
            validators.validate_phone("555-0100")

    def test_email_is_lowercased(self):
        assert validators.validate_email("  Maria@Example.COM ") == "maria@example.com"

    def test_email_rejects_garbage(self):
        with pytest.raises(ValidationError):
            validators.validate_email("not-an-email")

    def test_birth_date_in_future_rejected(self):
        with pytest.raises(ValidationError):
            validators.validate_birth_date(date(2030, 1, 1), date(2026, 3, 2))

    def test_require_text_strips_and_limits(self):
        assert validators.require_text("  Ana ", "name") == "Ana"
        with pytest.raises(ValidationError):
            validators.require_text("   ", "name")
        with pytest.raises(ValidationError):
            validators.require_text("x" * 100, "name")


class TestMoneyAndIds:
    def test_percent_of_rounds_half_up(self):
        assert percent_of(1_001, 50) == 501
        assert percent_of(10_000, 80) == 8_000

    def test_percent_of_validates(self):
        with pytest.raises(ValueError):
            percent_of(100, 101)

    def test_format_cents(self):
        assert format_cents(123456) == "$1,234.56"
        assert format_cents(-5) == "-$0.05"

    def test_id_generator_counts_per_prefix(self):
        ids = IdGenerator()
        assert ids.next("PAT") == "PAT-00001"
        assert ids.next("PAT") == "PAT-00002"
        assert ids.next("APT") == "APT-00001"
