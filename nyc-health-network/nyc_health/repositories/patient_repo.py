from typing import List, Optional

from nyc_health.models.patient import Borough, Patient
from nyc_health.repositories.base import InMemoryRepository


class PatientRepository(InMemoryRepository[Patient]):
    entity_name = "patient"
    id_prefix = "PAT"

    def find_by_phone(self, phone: str) -> Optional[Patient]:
        matches = self.find(lambda p: p.phone == phone)
        return matches[0] if matches else None

    def search_by_last_name(self, fragment: str) -> List[Patient]:
        needle = fragment.strip().lower()
        return sorted(
            self.find(lambda p: needle in p.last_name.lower()),
            key=lambda p: (p.last_name.lower(), p.first_name.lower()),
        )

    def in_borough(self, borough: Borough) -> List[Patient]:
        return self.find(lambda p: p.borough is borough)
