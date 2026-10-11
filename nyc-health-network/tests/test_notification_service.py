from datetime import date

from nyc_health.models.notification import NotificationChannel
from tests.conftest import at


def test_notification_uses_preferred_channel(container, doctor, patient):
    container.patients.update_contact(patient.id, preferred_channel=NotificationChannel.EMAIL)
    container.scheduling.book(patient.id, doctor.id, at(9))
    assert container.notifications.outbox_for(patient.id)[0].channel is NotificationChannel.EMAIL


def test_cancellation_notice_mentions_date(container, doctor, patient):
    appt = container.scheduling.book(patient.id, doctor.id, at(9))
    container.scheduling.cancel(appt.id)
    body = container.notifications.outbox_for(patient.id)[-1].body
    assert "Mar 03" in body and "cancelled" in body


def test_mark_sent(container, doctor, patient):
    container.scheduling.book(patient.id, doctor.id, at(9))
    notification = container.notifications.outbox_for(patient.id)[0]
    assert notification.status == "QUEUED"
    assert container.notifications.mark_sent(notification.id).status == "SENT"


def test_outbox_is_per_patient(container, doctor, patient, other_patient):
    container.scheduling.book(patient.id, doctor.id, at(9))
    assert container.notifications.outbox_for(other_patient.id) == []
