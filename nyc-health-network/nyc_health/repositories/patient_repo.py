from typing import List, Optional

from nyc_health.models.patient import Borough, Patient
from nyc_health.repositories.base import MongoRepository


class PatientRepository(MongoRepository[Patient]):
    entity_name = "patient"
    id_prefix = "PAT"
    collection_name = "patients"
    model = Patient
    indexes = [("phone",)]

    def find_by_phone(self, phone: str) -> Optional[Patient]:
        matches = self.find_where({"phone": phone}, limit=1)
        return matches[0] if matches else None

    def search_by_last_name(self, fragment: str) -> List[Patient]:
        needle = fragment.strip().lower()
        return sorted(
            self.find(lambda p: needle in p.last_name.lower()),
            key=lambda p: (p.last_name.lower(), p.first_name.lower()),
        )

    def in_borough(self, borough: Borough) -> List[Patient]:
        return self.find_where({"borough": borough.value})
