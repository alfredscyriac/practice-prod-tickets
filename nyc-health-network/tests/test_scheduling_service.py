from datetime import timedelta

import pytest

from nyc_health.exceptions import NotFoundError, SchedulingConflictError, ValidationError
from nyc_health.models.appointment import AppointmentStatus
from tests.conftest import BOOKING_DAY, at


class TestBooking:
    def test_book_creates_scheduled_appointment(self, container, doctor, patient):
        appt = container.scheduling.book(patient.id, doctor.id, at(9), 30, "CONSULT")
        assert appt.status is AppointmentStatus.SCHEDULED
        assert appt.end == at(9, 30)
        assert appt.hospital_id == doctor.hospital_id

    def test_booking_publishes_event_and_notifies_patient(self, container, doctor, patient):
        container.scheduling.book(patient.id, doctor.id, at(9))
        assert len(container.events.events_named("appointment.booked")) == 1
        outbox = container.notifications.outbox_for(patient.id)
        assert [n.subject for n in outbox] == ["Appointment confirmed"]

    def test_cannot_book_non_doctor(self, container, nurse, patient):
        with pytest.raises(ValidationError):
            container.scheduling.book(patient.id, nurse.id, at(9))

    def test_unknown_patient(self, container, doctor):
        with pytest.raises(NotFoundError):
            container.scheduling.book("PAT-404", doctor.id, at(9))

    def test_unknown_procedure(self, container, doctor, patient):
        with pytest.raises(ValidationError):
            container.scheduling.book(patient.id, doctor.id, at(9), procedure_code="TELEPORT")

    @pytest.mark.parametrize("duration", [0, 15, 45, 150])
    def test_invalid_durations(self, container, doctor, patient, duration):
        with pytest.raises(ValidationError):
            container.scheduling.book(patient.id, doctor.id, at(9), duration)

    def test_start_must_be_slot_aligned(self, container, doctor, patient):
        with pytest.raises(ValidationError):
            container.scheduling.book(patient.id, doctor.id, at(9, 10))

    def test_lead_time_enforced(self, container, clock, doctor, patient):
        clock.set(at(8, 30))
        with pytest.raises(ValidationError):
            container.scheduling.book(patient.id, doctor.id, at(9))

    def test_outside_business_hours(self, container, doctor, patient):
        with pytest.raises(SchedulingConflictError):
            container.scheduling.book(patient.id, doctor.id, at(17, 30), 60)

    def test_doctor_must_be_on_shift(self, container, patient, second_doctor):
        next_day = BOOKING_DAY + timedelta(days=1)
        with pytest.raises(SchedulingConflictError):
            container.scheduling.book(patient.id, second_doctor.id, at(9, day=next_day))


class TestConflicts:
    def test_same_slot_rejected_for_doctor(self, container, doctor, patient, other_patient):
        container.scheduling.book(patient.id, doctor.id, at(9), 60)
        with pytest.raises(SchedulingConflictError):
            container.scheduling.book(other_patient.id, doctor.id, at(9), 30)

    def test_partial_overlap_rejected(self, container, doctor, patient, other_patient):
        container.scheduling.book(patient.id, doctor.id, at(9), 60)
        with pytest.raises(SchedulingConflictError):
            container.scheduling.book(other_patient.id, doctor.id, at(9, 30), 60)

    def test_back_to_back_is_fine(self, container, doctor, patient, other_patient):
        container.scheduling.book(patient.id, doctor.id, at(9), 30)
        container.scheduling.book(other_patient.id, doctor.id, at(9, 30), 30)

    def test_patient_cannot_be_in_two_places(self, container, doctor, second_doctor, patient):
        container.scheduling.book(patient.id, doctor.id, at(9), 60)
        with pytest.raises(SchedulingConflictError):
            container.scheduling.book(patient.id, second_doctor.id, at(9, 30), 30)

    def test_cancelled_appointments_free_the_slot(self, container, doctor, patient, other_patient):
        appt = container.scheduling.book(patient.id, doctor.id, at(9), 30)
        container.scheduling.cancel(appt.id)
        container.scheduling.book(other_patient.id, doctor.id, at(9), 30)

    def test_daily_capacity_limit(self, container, doctor, patient, monkeypatch):
        monkeypatch.setattr("nyc_health.config.MAX_DAILY_APPOINTMENTS_PER_DOCTOR", 2)
        container.scheduling.book(patient.id, doctor.id, at(9))
        container.scheduling.book(patient.id, doctor.id, at(10))
        with pytest.raises(SchedulingConflictError):
            container.scheduling.book(patient.id, doctor.id, at(11))


class TestLifecycle:
    def test_cancel_publishes_event_with_reason(self, container, doctor, patient):
        appt = container.scheduling.book(patient.id, doctor.id, at(9))
        container.scheduling.cancel(appt.id, reason="patient request")
        payload = container.events.events_named("appointment.cancelled")[0]
        assert payload["reason"] == "patient request"
        assert payload["appointment_id"] == appt.id

    def test_cannot_cancel_twice(self, container, doctor, patient):
        appt = container.scheduling.book(patient.id, doctor.id, at(9))
        container.scheduling.cancel(appt.id)
        with pytest.raises(ValidationError):
            container.scheduling.cancel(appt.id)

    def test_check_in_then_complete(self, container, doctor, patient):
        appt = container.scheduling.book(patient.id, doctor.id, at(9))
        container.scheduling.check_in(appt.id)
        done = container.scheduling.complete(appt.id, notes="all clear")
        assert done.status is AppointmentStatus.COMPLETED
        assert done.notes == "all clear"

    def test_cannot_complete_without_check_in(self, container, doctor, patient):
        appt = container.scheduling.book(patient.id, doctor.id, at(9))
        with pytest.raises(ValidationError):
            container.scheduling.complete(appt.id)

    def test_no_show_only_after_start(self, container, clock, doctor, patient):
        appt = container.scheduling.book(patient.id, doctor.id, at(9))
        with pytest.raises(ValidationError):
            container.scheduling.mark_no_show(appt.id)
        clock.set(at(9, 45))
        assert container.scheduling.mark_no_show(appt.id).status is AppointmentStatus.NO_SHOW

    def test_reschedule_moves_appointment_and_notifies(self, container, doctor, patient):
        appt = container.scheduling.book(patient.id, doctor.id, at(9))
        moved = container.scheduling.reschedule(appt.id, at(14))
        assert moved.start == at(14)
        subjects = [n.subject for n in container.notifications.outbox_for(patient.id)]
        assert subjects == ["Appointment confirmed", "Appointment moved"]

    def test_reschedule_can_overlap_itself(self, container, doctor, patient):
        appt = container.scheduling.book(patient.id, doctor.id, at(9), 60)
        moved = container.scheduling.reschedule(appt.id, at(9, 30))
        assert moved.start == at(9, 30)

    def test_reschedule_conflict(self, container, doctor, patient, other_patient):
        container.scheduling.book(other_patient.id, doctor.id, at(14), 30)
        appt = container.scheduling.book(patient.id, doctor.id, at(9))
        with pytest.raises(SchedulingConflictError):
            container.scheduling.reschedule(appt.id, at(14))


class TestAvailability:
    def test_available_slots_exclude_booked_and_off_shift(self, container, doctor, patient):
        container.scheduling.book(patient.id, doctor.id, at(9), 60)
        slots = container.scheduling.available_slots(doctor.id, BOOKING_DAY, 30)
        assert at(8) in slots
        assert at(9) not in slots and at(9, 30) not in slots
        assert at(10) in slots
        assert at(17, 30) in slots

    def test_available_slots_respect_lead_time(self, container, clock, doctor):
        clock.set(at(8, 15))
        slots = container.scheduling.available_slots(doctor.id, BOOKING_DAY, 30)
        assert slots[0] == at(9, 30)

    def test_agenda_is_sorted(self, container, doctor, patient, other_patient):
        late = container.scheduling.book(patient.id, doctor.id, at(15))
        early = container.scheduling.book(other_patient.id, doctor.id, at(9))
        assert [a.id for a in container.scheduling.agenda_for_doctor(doctor.id, BOOKING_DAY)] == [early.id, late.id]


def test_complete_persists_notes(container, doctor, patient):
    appointment = container.scheduling.book(patient.id, doctor.id, at(10))
    container.scheduling.check_in(appointment.id)
    container.scheduling.complete(appointment.id, notes="stable, follow up in 6 weeks")
    assert container.appointments_repo.get(appointment.id).notes == "stable, follow up in 6 weeks"
