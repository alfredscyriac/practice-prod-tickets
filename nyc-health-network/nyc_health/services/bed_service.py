import json
from typing import Dict, Optional, Tuple

from nyc_health import config
from nyc_health.core.clock import Clock
from nyc_health.core.event_bus import EventBus
from nyc_health.db import FakeRedis
from nyc_health.exceptions import CapacityError, ValidationError
from nyc_health.models.bed import Admission, Bed, WardType
from nyc_health.repositories.bed_repo import AdmissionRepository, BedRepository
from nyc_health.repositories.patient_repo import PatientRepository


class BedService:
    """Admits and discharges inpatients and keeps bed occupancy consistent."""

    def __init__(
        self,
        beds: BedRepository,
        admissions: AdmissionRepository,
        patients: PatientRepository,
        cache: FakeRedis,
        events: EventBus,
        clock: Clock,
    ) -> None:
        self._beds = beds
        self._admissions = admissions
        self._patients = patients
        self._cache = cache
        self._events = events
        self._clock = clock

    def add_bed(self, hospital_id: str, ward: WardType, label: str) -> Bed:
        bed = Bed(id=self._beds.next_id(), hospital_id=hospital_id, ward=ward, label=label)
        self._beds.add(bed)
        self._invalidate_occupancy(hospital_id)
        return bed

    def admit(self, patient_id: str, hospital_id: str, ward: WardType, reason: str = "") -> Admission:
        patient = self._patients.get(patient_id)
        if self._admissions.active_for_patient(patient_id):
            raise ValidationError(f"patient {patient_id} is already admitted")
        if patient.is_infectious and ward is not WardType.ISOLATION:
            raise ValidationError("infectious patients must be admitted to an isolation ward")
        bed = self._beds.first_free(hospital_id, ward)
        if bed is None:
            raise CapacityError(f"no free {ward.value} beds at {hospital_id}")

        admission = Admission(
            id=self._admissions.next_id(),
            patient_id=patient_id,
            hospital_id=hospital_id,
            bed_id=bed.id,
            admitted_at=self._clock.now(),
            reason=reason,
        )
        self._admissions.add(admission)
        bed.occupied_by = admission.id
        self._beds.update(bed)
        self._invalidate_occupancy(hospital_id)
        self._events.publish(
            "patient.admitted",
            {"admission_id": admission.id, "patient_id": patient_id, "ward": ward.value, "bed_id": bed.id},
        )
        return admission

    def discharge(self, admission_id: str) -> Admission:
        admission = self._admissions.get(admission_id)
        if not admission.is_active:
            raise ValidationError(f"admission {admission_id} was already discharged")
        admission.discharged_at = self._clock.now()
        self._admissions.update(admission)
        bed = self._beds.get(admission.bed_id)
        bed.occupied_by = None
        self._beds.update(bed)
        self._invalidate_occupancy(admission.hospital_id)
        self._events.publish(
            "patient.discharged", {"admission_id": admission.id, "patient_id": admission.patient_id}
        )
        return admission

    def current_bed_for(self, patient_id: str) -> Optional[Bed]:
        admission = self._admissions.active_for_patient(patient_id)
        return self._beds.get(admission.bed_id) if admission else None

    def occupancy(self, hospital_id: str) -> Dict[WardType, Tuple[int, int]]:
        """Return {ward: (occupied, total)} for every ward that has at least one bed."""
        key = self._occupancy_key(hospital_id)
        cached = self._cache.get(key)
        if cached is not None:
            return {WardType(ward): (occ, total) for ward, (occ, total) in json.loads(cached).items()}
        summary: Dict[WardType, Tuple[int, int]] = {}
        for bed in self._beds.in_hospital(hospital_id):
            occupied, total = summary.get(bed.ward, (0, 0))
            summary[bed.ward] = (occupied + (0 if bed.is_free else 1), total + 1)
        self._cache.setex(
            key, config.OCCUPANCY_CACHE_TTL_SECONDS,
            json.dumps({ward.value: list(counts) for ward, counts in summary.items()}),
        )
        return summary

    @staticmethod
    def _occupancy_key(hospital_id: str) -> str:
        return f"occupancy:{hospital_id}"

    def _invalidate_occupancy(self, hospital_id: str) -> None:
        self._cache.delete(self._occupancy_key(hospital_id))
