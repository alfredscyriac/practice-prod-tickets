import pytest

from nyc_health.exceptions import CapacityError, NotFoundError, ValidationError
from nyc_health.models.bed import WardType

HOSPITAL = "H-BELLEVUE"


@pytest.fixture
def ward(container):
    container.beds.add_bed(HOSPITAL, WardType.GENERAL, "GEN-01")
    container.beds.add_bed(HOSPITAL, WardType.GENERAL, "GEN-02")
    container.beds.add_bed(HOSPITAL, WardType.ISOLATION, "ISO-01")
    container.beds.add_bed(HOSPITAL, WardType.ICU, "ICU-01")


def test_admit_assigns_first_free_bed(container, ward, patient):
    admission = container.beds.admit(patient.id, HOSPITAL, WardType.GENERAL, "chest pain")
    bed = container.beds_repo.get(admission.bed_id)
    assert bed.label == "GEN-01"
    assert bed.occupied_by == admission.id


def test_second_patient_gets_next_bed(container, ward, patient, other_patient):
    container.beds.admit(patient.id, HOSPITAL, WardType.GENERAL)
    second = container.beds.admit(other_patient.id, HOSPITAL, WardType.GENERAL)
    assert container.beds_repo.get(second.bed_id).label == "GEN-02"


def test_cannot_admit_twice(container, ward, patient):
    container.beds.admit(patient.id, HOSPITAL, WardType.GENERAL)
    with pytest.raises(ValidationError):
        container.beds.admit(patient.id, HOSPITAL, WardType.ICU)


def test_capacity_error_when_ward_full(container, ward, patient, other_patient):
    container.beds.admit(patient.id, HOSPITAL, WardType.ICU)
    with pytest.raises(CapacityError):
        container.beds.admit(other_patient.id, HOSPITAL, WardType.ICU)


def test_infectious_patients_only_go_to_isolation(container, ward, patient):
    container.patients.flag_infectious(patient.id, True)
    with pytest.raises(ValidationError):
        container.beds.admit(patient.id, HOSPITAL, WardType.GENERAL)
    admission = container.beds.admit(patient.id, HOSPITAL, WardType.ISOLATION)
    assert container.beds.current_bed_for(patient.id).label == "ISO-01"
    assert admission.is_active


def test_discharge_frees_bed_and_stamps_time(container, clock, ward, patient):
    admission = container.beds.admit(patient.id, HOSPITAL, WardType.GENERAL)
    clock.advance(hours=30)
    discharged = container.beds.discharge(admission.id)
    assert discharged.length_of_stay_hours(clock.now()) == 30.0
    assert container.beds_repo.get(admission.bed_id).is_free
    assert container.beds.current_bed_for(patient.id) is None


def test_cannot_discharge_twice(container, ward, patient):
    admission = container.beds.admit(patient.id, HOSPITAL, WardType.GENERAL)
    container.beds.discharge(admission.id)
    with pytest.raises(ValidationError):
        container.beds.discharge(admission.id)


def test_readmission_after_discharge(container, ward, patient):
    first = container.beds.admit(patient.id, HOSPITAL, WardType.GENERAL)
    container.beds.discharge(first.id)
    container.beds.admit(patient.id, HOSPITAL, WardType.GENERAL)
    assert len(container.admissions_repo.history_for_patient(patient.id)) == 2


def test_occupancy_summary(container, ward, patient):
    container.beds.admit(patient.id, HOSPITAL, WardType.GENERAL)
    assert container.beds.occupancy(HOSPITAL) == {
        WardType.GENERAL: (1, 2), WardType.ISOLATION: (0, 1), WardType.ICU: (0, 1),
    }


def test_unknown_admission(container):
    with pytest.raises(NotFoundError):
        container.beds.discharge("ADM-404")
