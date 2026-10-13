from typing import List

from nyc_health.models.notification import Notification
from nyc_health.repositories.base import MongoRepository


class NotificationRepository(MongoRepository[Notification]):
    entity_name = "notification"
    id_prefix = "NTF"
    collection_name = "notifications"
    model = Notification
    indexes = [("patient_id",)]

    def for_patient(self, patient_id: str) -> List[Notification]:
        return self.find_where({"patient_id": patient_id}, sort=[("created_at", 1)])
