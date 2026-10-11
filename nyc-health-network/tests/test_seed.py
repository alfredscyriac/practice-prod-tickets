from datetime import date

from nyc_health.models.bed import WardType
from nyc_health.seed import seed
from tests.conftest import BOOKING_DAY


def test_seed_populates_all_entities(container):
    data = seed(container, BOOKING_DAY)
    assert len(data["doctors"]) == 5
    assert len(data["patients"]) == 4
    assert container.beds.occupancy("H-BELLEVUE")[WardType.ICU] == (0, 2)
    assert all(container.shifts.shifts_for(d.id) for d in data["doctors"])


def test_seeded_doctor_has_open_slots(container):
    data = seed(container, BOOKING_DAY)
    slots = container.scheduling.available_slots(data["doctors"][0].id, BOOKING_DAY)
    assert len(slots) == 20
