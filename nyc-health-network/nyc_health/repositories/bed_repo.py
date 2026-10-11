from typing import List, Optional

from nyc_health.models.bed import Admission, Bed, WardType
from nyc_health.repositories.base import InMemoryRepository


class BedRepository(InMemoryRepository[Bed]):
    entity_name = "bed"
    id_prefix = "BED"

    def in_hospital(self, hospital_id: str, ward: Optional[WardType] = None) -> List[Bed]:
        return sorted(
            self.find(lambda b: b.hospital_id == hospital_id and (ward is None or b.ward is ward)),
            key=lambda b: b.label,
        )

    def first_free(self, hospital_id: str, ward: WardType) -> Optional[Bed]:
        for bed in self.in_hospital(hospital_id, ward):
            if bed.is_free:
                return bed
        return None


class AdmissionRepository(InMemoryRepository[Admission]):
    entity_name = "admission"
    id_prefix = "ADM"

    def active_for_patient(self, patient_id: str) -> Optional[Admission]:
        matches = self.find(lambda a: a.patient_id == patient_id and a.is_active)
        return matches[0] if matches else None

    def active_in_hospital(self, hospital_id: str) -> List[Admission]:
        return self.find(lambda a: a.hospital_id == hospital_id and a.is_active)

    def history_for_patient(self, patient_id: str) -> List[Admission]:
        return sorted(self.find(lambda a: a.patient_id == patient_id), key=lambda a: a.admitted_at)
