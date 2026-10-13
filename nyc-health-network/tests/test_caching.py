from nyc_health import config
from nyc_health.models.bed import WardType


def test_patient_get_populates_cache(container, patient):
    container.cache.flushall()
    container.patients.get(patient.id)
    assert container.cache.exists(f"patient:{patient.id}")


def test_patient_cache_is_invalidated_on_update(container, patient):
    container.patients.get(patient.id)
    container.patients.update_contact(patient.id, email="new@example.com")
    assert container.patients.get(patient.id).email == "new@example.com"


def test_patient_cache_expires(container, clock, patient):
    container.patients.get(patient.id)
    clock.advance(seconds=config.PATIENT_CACHE_TTL_SECONDS + 1)
    assert not container.cache.exists(f"patient:{patient.id}")


def test_occupancy_is_cached_and_invalidated_by_admit_and_discharge(container, patient):
    container.beds.add_bed("H-BELLEVUE", WardType.GENERAL, "GEN-01")
    assert container.beds.occupancy("H-BELLEVUE")[WardType.GENERAL] == (0, 1)
    container.db.reset_stats()
    container.beds.occupancy("H-BELLEVUE")
    assert container.db.stats.queries == 0  # served from Redis

    admission = container.beds.admit(patient.id, "H-BELLEVUE", WardType.GENERAL)
    assert container.beds.occupancy("H-BELLEVUE")[WardType.GENERAL] == (1, 1)
    container.beds.discharge(admission.id)
    assert container.beds.occupancy("H-BELLEVUE")[WardType.GENERAL] == (0, 1)


def test_adding_a_bed_refreshes_cached_occupancy(container):
    container.beds.add_bed("H-BELLEVUE", WardType.ICU, "ICU-01")
    assert container.beds.occupancy("H-BELLEVUE")[WardType.ICU] == (0, 1)
    container.beds.add_bed("H-BELLEVUE", WardType.ICU, "ICU-02")
    assert container.beds.occupancy("H-BELLEVUE")[WardType.ICU] == (0, 2)
