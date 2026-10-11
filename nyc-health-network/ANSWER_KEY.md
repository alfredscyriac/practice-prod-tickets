# Answer key (do NOT read before attempting — use only to check your AI-assisted exploration)

The point of the exercise is to see whether you and your AI assistant can narrow a 45+ file repo down
to the handful of relevant files. This lists the "expected" scope per ticket.

## HN-412 (double booking)
Root cause: `utils/time_utils.py::intervals_overlap` misses the case where interval B fully contains A.
Callers: `services/scheduling_service.py` (doctor + patient checks), `services/shift_service.py`.
Fix: `a_start < b_end and b_start < a_end`. Tests: `tests/test_utils.py`, `test_scheduling_service.py`,
`test_shift_service.py`.
Distractors: `models/appointment.py`, `repositories/appointment_repo.py`, `api/handlers.py` (fine).

## HN-431 (deductible)
Root cause: `services/billing_service.py::finalize_invoice` calls the pure `calculate_claim` instead of
`apply_claim`, so `deductible_met_cents` is never persisted. Void must call `release_deductible` with
`invoice.deductible_applied_cents` (only for FINALIZED invoices). Idempotency: `_editable` already blocks
double finalize. Relevant: `services/insurance_service.py`, `models/insurance.py`, `models/billing.py`,
`repositories/insurance_repo.py`. Tests: `test_billing_service.py`, `test_insurance_service.py`.
Note `BillingService` needs the policy id for the patient on void — look it up via the insurance service
(consider whether an expired policy should still receive the credit).
Distractors: `services/reporting_service.py`, `services/patient_service.py`.

## HN-447 (waitlist)
New: `models/waitlist.py`, `repositories/waitlist_repo.py`, `services/waitlist_service.py`; wire up in
`container.py`; subscribe to `appointment.cancelled` on the `EventBus` (`core/event_bus.py`); booking via
`SchedulingService.book` (watch out for the 60-minute lead-time rule and duplicate-event/recursion cases);
notify via `NotificationService.send`. Tests: new `tests/test_waitlist_service.py`.
Distractors: `bed_service.py`, `billing_service.py`, `insurance_service.py`.

## HN-455 (ward transfer)
Touches: `models/bed.py` (new `Transfer` record), `repositories/bed_repo.py` (transfer storage/query),
`services/bed_service.py` (`transfer`), `container.py` if a new repo is added. Reuse the infectious-patient
rule from `admit`. Must be atomic: validate everything before mutating beds. Tests: `tests/test_bed_service.py`.
Distractors: `scheduling_service.py`, billing, insurance.
