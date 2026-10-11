from typing import List

from nyc_health.models.notification import Notification
from nyc_health.repositories.base import InMemoryRepository


class NotificationRepository(InMemoryRepository[Notification]):
    entity_name = "notification"
    id_prefix = "NTF"

    def for_patient(self, patient_id: str) -> List[Notification]:
        return sorted(self.find(lambda n: n.patient_id == patient_id), key=lambda n: n.created_at)
