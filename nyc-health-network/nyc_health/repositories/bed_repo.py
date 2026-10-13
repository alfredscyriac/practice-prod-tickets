from typing import List, Optional

from nyc_health.models.bed import Admission, Bed, WardType
from nyc_health.repositories.base import MongoRepository


class BedRepository(MongoRepository[Bed]):
    entity_name = "bed"
    id_prefix = "BED"
    collection_name = "beds"
    model = Bed
    indexes = [("hospital_id", "ward")]

    def in_hospital(self, hospital_id: str, ward: Optional[WardType] = None) -> List[Bed]:
        flt = {"hospital_id": hospital_id}
        if ward is not None:
            flt["ward"] = ward.value
        return self.find_where(flt, sort=[("label", 1)])

    def first_free(self, hospital_id: str, ward: WardType) -> Optional[Bed]:
        beds = self.find_where(
            {"hospital_id": hospital_id, "ward": ward.value, "occupied_by": None}, sort=[("label", 1)], limit=1
        )
        return beds[0] if beds else None


class AdmissionRepository(MongoRepository[Admission]):
    entity_name = "admission"
    id_prefix = "ADM"
    collection_name = "admissions"
    model = Admission
    indexes = [("patient_id",), ("hospital_id",)]

    def active_for_patient(self, patient_id: str) -> Optional[Admission]:
        matches = self.find_where({"patient_id": patient_id, "discharged_at": None})
        return matches[0] if matches else None

    def active_in_hospital(self, hospital_id: str) -> List[Admission]:
        return self.find_where({"hospital_id": hospital_id, "discharged_at": None})

    def history_for_patient(self, patient_id: str) -> List[Admission]:
        return self.find_where({"patient_id": patient_id}, sort=[("admitted_at", 1)])
