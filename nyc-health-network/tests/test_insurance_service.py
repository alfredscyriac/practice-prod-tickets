from datetime import date

import pytest

from nyc_health.exceptions import BillingError
from nyc_health.models.insurance import InsurancePolicy


def make_policy(**overrides) -> InsurancePolicy:
    params = dict(
        id="POL-1", patient_id="PAT-1", plan_name="Test", member_id="M-1", coverage_pct=80,
        copay_cents=3_000, deductible_cents=150_000, expires_on=date(2026, 12, 31),
    )
    params.update(overrides)
    return InsurancePolicy(**params)


def test_charge_below_deductible_is_all_patient(container):
    claim = container.insurance.calculate_claim(make_policy(), 25_000)
    assert claim.deductible_applied_cents == 25_000
    assert claim.copay_cents == 0
    assert claim.insurer_pays_cents == 0
    assert claim.patient_owes_cents == 25_000


def test_charge_above_deductible_splits_copay_and_coinsurance(container):
    policy = make_policy(deductible_met_cents=150_000)
    claim = container.insurance.calculate_claim(policy, 100_000)
    assert claim.deductible_applied_cents == 0
    assert claim.copay_cents == 3_000
    assert claim.insurer_pays_cents == 77_600
    assert claim.coinsurance_cents == 19_400
    assert claim.patient_owes_cents + claim.insurer_pays_cents == 100_000


def test_partial_deductible_remaining(container):
    policy = make_policy(deductible_met_cents=140_000)
    claim = container.insurance.calculate_claim(policy, 25_000)
    assert claim.deductible_applied_cents == 10_000
    assert claim.copay_cents == 3_000
    assert claim.insurer_pays_cents == 9_600
    assert claim.patient_owes_cents == 15_400


def test_copay_never_exceeds_charge(container):
    policy = make_policy(deductible_met_cents=150_000)
    claim = container.insurance.calculate_claim(policy, 1_500)
    assert claim.copay_cents == 1_500
    assert claim.patient_owes_cents == 1_500


def test_negative_charge_rejected(container):
    with pytest.raises(BillingError):
        container.insurance.calculate_claim(make_policy(), -1)


def test_calculate_claim_is_pure(container):
    policy = make_policy()
    container.insurance.calculate_claim(policy, 50_000)
    assert policy.deductible_met_cents == 0


def test_get_active_policy_ignores_expired(container, patient):
    container.patients.attach_insurance(patient.id, "Plan", "M-9", date(2026, 3, 10))
    assert container.insurance.get_active_policy_for_patient(patient.id, date(2026, 3, 10)) is not None
    assert container.insurance.get_active_policy_for_patient(patient.id, date(2026, 3, 11)) is None


def test_apply_claim_records_deductible(container, insured_patient):
    policy_id = insured_patient.insurance_policy_id
    claim = container.insurance.apply_claim(policy_id, 25_000)
    assert claim.deductible_applied_cents == 25_000
    assert container.policies_repo.get(policy_id).deductible_met_cents == 25_000


def test_release_deductible_never_goes_negative(container, insured_patient):
    policy_id = insured_patient.insurance_policy_id
    container.insurance.apply_claim(policy_id, 10_000)
    policy = container.insurance.release_deductible(policy_id, 50_000)
    assert policy.deductible_met_cents == 0
