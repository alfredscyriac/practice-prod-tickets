from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class NotificationChannel(Enum):
    SMS = "sms"
    EMAIL = "email"


@dataclass
class Notification:
    id: str
    patient_id: str
    channel: NotificationChannel
    subject: str
    body: str
    created_at: datetime
    status: str = "QUEUED"
