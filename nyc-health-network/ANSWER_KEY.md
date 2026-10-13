# Answer key (do NOT read before attempting — use only to check your AI-assisted exploration)

The point of the exercise is to see whether you and your AI assistant can narrow a 50+ file repo down
to the handful of relevant files. This lists the "expected" scope per ticket.

Ticket types: HN-412 and HN-431 are straightforward root-cause bugs. HN-447 and HN-455 are the
**system-design** tickets (idempotency, indexing, atomic claims, cache invalidation).

## HN-412 (double booking) — bug
Root cause: `utils/time_utils.py::intervals_overlap` misses the case where interval B fully contains A
(`a_start <= b_start < a_end or a_start < b_end <= a_end`).
Callers: `services/scheduling_service.py` (doctor + patient checks), `services/shift_service.py`.
Fix: `a_start < b_end and b_start < a_end`. Write new tests: `tests/test_utils.py` (containment, both
orders), `test_scheduling_service.py`, `test_shift_service.py`.
Distractors: `models/appointment.py`, `repositories/appointment_repo.py`, `api/handlers.py`, the `db/` package.

## HN-431 (deductible) — bug
Root cause: `services/billing_service.py::finalize_invoice` calls the pure `calculate_claim` instead of
`apply_claim`, so `deductible_met_cents` is never persisted. Void must call `release_deductible` with
`invoice.deductible_applied_cents` (only for FINALIZED invoices). Idempotency: `_editable` already blocks
double finalize. Relevant: `services/insurance_service.py`, `models/insurance.py`, `models/billing.py`,
`repositories/insurance_repo.py`. Tests: `test_billing_service.py`, `test_insurance_service.py`.
`BillingService.void_invoice` needs the policy id for the patient — look it up via the insurance service
(consider whether an expired policy should still receive the credit).
Gotcha: repositories return COPIES (document store). Mutating a policy without `update()` silently
loses the change; that is also why the bug is invisible without a multi-invoice test.
Distractors: `services/reporting_service.py`, `services/patient_service.py` (Redis patient cache is not involved).

## HN-447 (waitlist) — system design
New: `models/waitlist.py`, `repositories/waitlist_repo.py`, `services/waitlist_service.py`; wire up in
`container.py` (pass `db`, `cache`); subscribe to `appointment.cancelled` on the `EventBus`
(`core/event_bus.py`); book via `SchedulingService.book` (watch the 60-minute lead-time rule and
recursion: booking publishes `appointment.booked`; a failed candidate must not abort the loop);
notify via `NotificationService.send`. Tests: new `tests/test_waitlist_service.py`.
Design points a strong answer hits:
- **Index**: declare `indexes = [("doctor_id", "date")]` on the waitlist repo and query with
  `find_where({...}, sort=[("created_at", 1)])`; assert with `container.db.stats.docs_examined`
  (do NOT use `find(lambda ...)`, which loads every document).
- **Idempotency / concurrency**: dedupe redelivered events with `cache.set(f"waitlist:cancel:{appointment_id}", ..., nx=True, ex=TTL)`
  (or a unique index); the second delivery must be a no-op. Promote with an atomic claim (delete the
  waitlist entry first / `find_one_and_update`) so two workers cannot promote the same entry.
- **Ordering**: oldest request first (`created_at`, tie-break on id); skipped entries stay.
- **Failure isolation**: cancellation must succeed even if booking a candidate raises; handler
  exceptions must not propagate out of `EventBus.publish`.
- Freed window is `[start, end)` of the cancelled appointment, not the whole day.
Distractors: `bed_service.py`, `billing_service.py`, `insurance_service.py`, reporting.

## HN-455 (ward transfer) — system design
Touches: `models/bed.py` (new `Transfer` record), `repositories/bed_repo.py` (transfer collection +
atomic bed claim), `services/bed_service.py` (`transfer`), `container.py` if a new repo is added.
Design points:
- **Atomic claim**: `first_free` followed by `update` is a check-then-act race (and `admit` has the same
  weakness). Claim with `collection.find_one_and_update({"hospital_id", "ward", "occupied_by": None},
  {"$set": {"occupied_by": admission_id}}, sort=[("label", 1)])` and treat `None` as `CapacityError`.
  Test it with two transfers racing for the last bed (threads, or interleave two calls at the claim).
- **Ordering for atomicity**: validate everything first; claim the new bed; then update the admission;
  release the old bed last. If a later step fails, release the claimed bed (compensate).
- **Cache invalidation**: `occupancy` is cached in Redis (`occupancy:{hospital_id}`, 60s TTL). Transfer
  must invalidate it (`BedService._invalidate_occupancy`) — otherwise `ReportingService.occupancy_percentages`
  is stale. Within one hospital only that key is affected.
- Reuse the infectious-patient rule from `admit`. Store transfers in a new collection with an index on
  `(admission_id)` and read them sorted by timestamp.
Tests: `tests/test_bed_service.py` plus new transfer tests. Distractors: scheduling, billing, insurance.

## Repo-wide notes
- `db/mongo.py` and `db/redis.py` are the cheap stand-ins; `repositories/base.py::MongoRepository` is the
  seam. `container.db.stats` exposes docs examined / index hits / full scans for efficiency assertions.
- Redis is already used for `patient:{id}` and `occupancy:{hospital_id}` cache-aside reads.
