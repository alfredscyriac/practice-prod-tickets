from datetime import date
from typing import List, Optional

from nyc_health import config
from nyc_health.core.clock import Clock
from nyc_health.db import FakeRedis, codec
from nyc_health.exceptions import ValidationError
from nyc_health.models.insurance import InsurancePolicy
from nyc_health.models.notification import NotificationChannel
from nyc_health.models.patient import Borough, Patient
from nyc_health.repositories.insurance_repo import PolicyRepository
from nyc_health.repositories.patient_repo import PatientRepository
from nyc_health.utils import validators


class PatientService:
    def __init__(
        self, patients: PatientRepository, policies: PolicyRepository, cache: FakeRedis, clock: Clock
    ) -> None:
        self._patients = patients
        self._policies = policies
        self._cache = cache
        self._clock = clock

    def register(
        self,
        first_name: str,
        last_name: str,
        date_of_birth: date,
        phone: str,
        borough: Borough,
        email: Optional[str] = None,
    ) -> Patient:
        normalized_phone = validators.validate_phone(phone)
        if self._patients.find_by_phone(normalized_phone):
            raise ValidationError("a patient with this phone number already exists")
        patient = Patient(
            id=self._patients.next_id(),
            first_name=validators.require_text(first_name, "first name"),
            last_name=validators.require_text(last_name, "last name"),
            date_of_birth=validators.validate_birth_date(date_of_birth, self._clock.now().date()),
            phone=normalized_phone,
            borough=borough,
            email=validators.validate_email(email) if email else None,
        )
        return self._patients.add(patient)

    @staticmethod
    def _cache_key(patient_id: str) -> str:
        return f"patient:{patient_id}"

    def get(self, patient_id: str) -> Patient:
        """Cache-aside read: Redis first, then Mongo (and populate the cache)."""
        cached = self._cache.get(self._cache_key(patient_id))
        if cached is not None:
            return codec.loads(Patient, cached)
        patient = self._patients.get(patient_id)
        self._cache.setex(self._cache_key(patient_id), config.PATIENT_CACHE_TTL_SECONDS, codec.dumps(patient))
        return patient

    def update_contact(
        self,
        patient_id: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        preferred_channel: Optional[NotificationChannel] = None,
    ) -> Patient:
        patient = self._patients.get(patient_id)
        if phone is not None:
            patient.phone = validators.validate_phone(phone)
        if email is not None:
            patient.email = validators.validate_email(email)
        if preferred_channel is not None:
            if preferred_channel is NotificationChannel.EMAIL and not patient.email:
                raise ValidationError("cannot prefer email without an email address on file")
            patient.preferred_channel = preferred_channel
        self._cache.delete(self._cache_key(patient_id))
        return self._patients.update(patient)

    def flag_infectious(self, patient_id: str, infectious: bool) -> Patient:
        patient = self._patients.get(patient_id)
        patient.is_infectious = infectious
        self._cache.delete(self._cache_key(patient_id))
        return self._patients.update(patient)

    def attach_insurance(
        self,
        patient_id: str,
        plan_name: str,
        member_id: str,
        expires_on: date,
        copay_cents: int = 3_000,
        deductible_cents: int = 150_000,
        coverage_pct: int = config.DEFAULT_COVERAGE_PCT,
    ) -> InsurancePolicy:
        patient = self._patients.get(patient_id)
        if expires_on < self._clock.now().date():
            raise ValidationError("insurance policy is already expired")
        if not 0 <= coverage_pct <= 100:
            raise ValidationError("coverage must be between 0 and 100 percent")
        policy = InsurancePolicy(
            id=self._policies.next_id(),
            patient_id=patient.id,
            plan_name=validators.require_text(plan_name, "plan name"),
            member_id=validators.require_text(member_id, "member id", max_len=32),
            coverage_pct=coverage_pct,
            copay_cents=copay_cents,
            deductible_cents=deductible_cents,
            expires_on=expires_on,
        )
        self._policies.add(policy)
        patient.insurance_policy_id = policy.id
        self._patients.update(patient)
        self._cache.delete(self._cache_key(patient_id))
        return policy

    def search(self, last_name_fragment: str) -> List[Patient]:
        return self._patients.search_by_last_name(last_name_fragment)
