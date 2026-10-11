from typing import Any, Dict, List

from nyc_health.core.clock import Clock
from nyc_health.core.event_bus import EventBus
from nyc_health.models.notification import Notification
from nyc_health.repositories.notification_repo import NotificationRepository
from nyc_health.repositories.patient_repo import PatientRepository


class NotificationService:
    """Turns domain events into queued patient notifications (SMS/email outbox)."""

    def __init__(
        self,
        notifications: NotificationRepository,
        patients: PatientRepository,
        events: EventBus,
        clock: Clock,
    ) -> None:
        self._notifications = notifications
        self._patients = patients
        self._clock = clock
        events.subscribe("appointment.booked", self._on_booked)
        events.subscribe("appointment.rescheduled", self._on_rescheduled)
        events.subscribe("appointment.cancelled", self._on_cancelled)

    def send(self, patient_id: str, subject: str, body: str) -> Notification:
        patient = self._patients.get(patient_id)
        notification = Notification(
            id=self._notifications.next_id(),
            patient_id=patient.id,
            channel=patient.preferred_channel,
            subject=subject,
            body=body,
            created_at=self._clock.now(),
        )
        return self._notifications.add(notification)

    def outbox_for(self, patient_id: str) -> List[Notification]:
        return self._notifications.for_patient(patient_id)

    def mark_sent(self, notification_id: str) -> Notification:
        notification = self._notifications.get(notification_id)
        notification.status = "SENT"
        return self._notifications.update(notification)

    # -------------------------------------------------------------- subscribers
    def _on_booked(self, payload: Dict[str, Any]) -> None:
        self.send(
            payload["patient_id"],
            "Appointment confirmed",
            f"Your {payload['procedure_code']} appointment is booked for {payload['start']:%b %d at %I:%M %p}.",
        )

    def _on_rescheduled(self, payload: Dict[str, Any]) -> None:
        self.send(
            payload["patient_id"],
            "Appointment moved",
            f"Your appointment moved from {payload['previous_start']:%b %d %I:%M %p} "
            f"to {payload['start']:%b %d %I:%M %p}.",
        )

    def _on_cancelled(self, payload: Dict[str, Any]) -> None:
        self.send(
            payload["patient_id"],
            "Appointment cancelled",
            f"Your appointment on {payload['start']:%b %d at %I:%M %p} has been cancelled.",
        )
