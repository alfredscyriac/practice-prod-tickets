from datetime import date, datetime, timedelta
from typing import List, Optional

from nyc_health import config
from nyc_health.core.clock import Clock
from nyc_health.core.event_bus import EventBus
from nyc_health.exceptions import SchedulingConflictError, ValidationError
from nyc_health.models.appointment import Appointment, AppointmentStatus
from nyc_health.models.staff import Role, Staff
from nyc_health.repositories.appointment_repo import AppointmentRepository
from nyc_health.repositories.patient_repo import PatientRepository
from nyc_health.repositories.staff_repo import StaffRepository
from nyc_health.services.shift_service import ShiftService
from nyc_health.utils import time_utils
from nyc_health.utils.time_utils import intervals_overlap


class SchedulingService:
    """Books, moves and cancels appointments, enforcing doctor/patient availability."""

    def __init__(
        self,
        appointments: AppointmentRepository,
        patients: PatientRepository,
        staff: StaffRepository,
        shifts: ShiftService,
        events: EventBus,
        clock: Clock,
    ) -> None:
        self._appointments = appointments
        self._patients = patients
        self._staff = staff
        self._shifts = shifts
        self._events = events
        self._clock = clock

    # ------------------------------------------------------------------ booking
    def book(
        self,
        patient_id: str,
        doctor_id: str,
        start: datetime,
        duration_minutes: int = config.APPOINTMENT_SLOT_MINUTES,
        procedure_code: str = "CONSULT",
    ) -> Appointment:
        self._patients.get(patient_id)
        doctor = self._require_doctor(doctor_id)
        if procedure_code not in config.PROCEDURE_PRICES_CENTS:
            raise ValidationError(f"unknown procedure code '{procedure_code}'")
        end = self._validate_window(start, duration_minutes)
        self._ensure_doctor_available(doctor, start, end)
        self._ensure_patient_available(patient_id, start, end)

        appointment = Appointment(
            id=self._appointments.next_id(),
            patient_id=patient_id,
            doctor_id=doctor.id,
            hospital_id=doctor.hospital_id,
            start=start,
            duration_minutes=duration_minutes,
            procedure_code=procedure_code,
            created_at=self._clock.now(),
        )
        self._appointments.add(appointment)
        self._events.publish("appointment.booked", self._event_payload(appointment))
        return appointment

    def reschedule(
        self, appointment_id: str, new_start: datetime, duration_minutes: Optional[int] = None
    ) -> Appointment:
        appointment = self._appointments.get(appointment_id)
        if not appointment.is_active:
            raise ValidationError("only active appointments can be rescheduled")
        duration = duration_minutes or appointment.duration_minutes
        doctor = self._require_doctor(appointment.doctor_id)
        new_end = self._validate_window(new_start, duration)
        self._ensure_doctor_available(doctor, new_start, new_end, exclude_id=appointment.id)
        self._ensure_patient_available(appointment.patient_id, new_start, new_end, exclude_id=appointment.id)

        previous_start = appointment.start
        appointment.start = new_start
        appointment.duration_minutes = duration
        self._appointments.update(appointment)
        payload = self._event_payload(appointment)
        payload["previous_start"] = previous_start
        self._events.publish("appointment.rescheduled", payload)
        return appointment

    def cancel(self, appointment_id: str, reason: str = "") -> Appointment:
        appointment = self._appointments.get(appointment_id)
        appointment.transition_to(AppointmentStatus.CANCELLED, self._clock.now())
        self._appointments.update(appointment)
        payload = self._event_payload(appointment)
        payload["reason"] = reason
        self._events.publish("appointment.cancelled", payload)
        return appointment

    # ----------------------------------------------------------- status changes
    def check_in(self, appointment_id: str) -> Appointment:
        return self._transition(appointment_id, AppointmentStatus.CHECKED_IN)

    def complete(self, appointment_id: str, notes: str = "") -> Appointment:
        appointment = self._transition(appointment_id, AppointmentStatus.COMPLETED)
        appointment.notes = notes
        self._events.publish("appointment.completed", self._event_payload(appointment))
        return appointment

    def mark_no_show(self, appointment_id: str) -> Appointment:
        appointment = self._appointments.get(appointment_id)
        if self._clock.now() < appointment.start:
            raise ValidationError("cannot mark a future appointment as a no-show")
        appointment = self._transition(appointment_id, AppointmentStatus.NO_SHOW)
        self._events.publish("appointment.no_show", self._event_payload(appointment))
        return appointment

    # ------------------------------------------------------------------ queries
    def available_slots(
        self, doctor_id: str, day: date, duration_minutes: int = config.APPOINTMENT_SLOT_MINUTES
    ) -> List[datetime]:
        doctor = self._require_doctor(doctor_id)
        earliest = self._clock.now() + timedelta(minutes=config.MIN_BOOKING_LEAD_MINUTES)
        open_slots: List[datetime] = []
        for start in time_utils.generate_slots(day, duration_minutes):
            end = start + timedelta(minutes=duration_minutes)
            if start < earliest or not self._shifts.is_on_duty(doctor.id, start, end):
                continue
            try:
                self._ensure_doctor_available(doctor, start, end)
            except SchedulingConflictError:
                continue
            open_slots.append(start)
        return open_slots

    def agenda_for_doctor(self, doctor_id: str, day: date) -> List[Appointment]:
        return self._appointments.active_for_doctor_on_day(doctor_id, day)

    def history_for_patient(self, patient_id: str) -> List[Appointment]:
        return self._appointments.for_patient(patient_id)

    # ------------------------------------------------------------------ helpers
    def _transition(self, appointment_id: str, status: AppointmentStatus) -> Appointment:
        appointment = self._appointments.get(appointment_id)
        appointment.transition_to(status, self._clock.now())
        return self._appointments.update(appointment)

    def _require_doctor(self, doctor_id: str) -> Staff:
        doctor = self._staff.get(doctor_id)
        if doctor.role is not Role.DOCTOR:
            raise ValidationError(f"staff member {doctor_id} is not a doctor")
        return doctor

    def _validate_window(self, start: datetime, duration_minutes: int) -> datetime:
        if duration_minutes <= 0 or duration_minutes % config.APPOINTMENT_SLOT_MINUTES:
            raise ValidationError(
                f"duration must be a positive multiple of {config.APPOINTMENT_SLOT_MINUTES} minutes"
            )
        if duration_minutes > config.MAX_APPOINTMENT_MINUTES:
            raise ValidationError(f"appointments are limited to {config.MAX_APPOINTMENT_MINUTES} minutes")
        if not time_utils.is_slot_aligned(start):
            raise ValidationError("start time must be aligned to a slot boundary")
        if start < self._clock.now() + timedelta(minutes=config.MIN_BOOKING_LEAD_MINUTES):
            raise ValidationError(
                f"appointments must be booked at least {config.MIN_BOOKING_LEAD_MINUTES} minutes ahead"
            )
        end = start + timedelta(minutes=duration_minutes)
        if not time_utils.within_business_hours(start, end):
            raise SchedulingConflictError("appointment falls outside business hours")
        return end

    def _ensure_doctor_available(
        self, doctor: Staff, start: datetime, end: datetime, exclude_id: Optional[str] = None
    ) -> None:
        if not self._shifts.is_on_duty(doctor.id, start, end):
            raise SchedulingConflictError(f"{doctor.name} is not on shift for that time")
        booked = [
            a for a in self._appointments.active_for_doctor_on_day(doctor.id, start.date())
            if a.id != exclude_id
        ]
        if len(booked) >= config.MAX_DAILY_APPOINTMENTS_PER_DOCTOR:
            raise SchedulingConflictError(f"{doctor.name} has no capacity left that day")
        for other in booked:
            if intervals_overlap(other.start, other.end, start, end):
                raise SchedulingConflictError(f"{doctor.name} already has an appointment at {other.start:%H:%M}")

    def _ensure_patient_available(
        self, patient_id: str, start: datetime, end: datetime, exclude_id: Optional[str] = None
    ) -> None:
        for other in self._appointments.active_for_patient_on_day(patient_id, start.date()):
            if other.id == exclude_id:
                continue
            if intervals_overlap(other.start, other.end, start, end):
                raise SchedulingConflictError("patient already has an overlapping appointment")

    @staticmethod
    def _event_payload(appointment: Appointment) -> dict:
        return {
            "appointment_id": appointment.id,
            "patient_id": appointment.patient_id,
            "doctor_id": appointment.doctor_id,
            "hospital_id": appointment.hospital_id,
            "start": appointment.start,
            "end": appointment.end,
            "procedure_code": appointment.procedure_code,
        }
