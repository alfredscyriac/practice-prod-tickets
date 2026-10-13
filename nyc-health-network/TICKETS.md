# Sprint Tickets — NYC Health Network

You have been assigned the tickets below. **Complete ONE** of them (your choice). Treat it the way
you would on the job: understand the problem, find the relevant code, make the change, and add or
update tests. The full existing test suite must still pass (`pytest`).

Ground rules
- There is **no failing test** waiting for you. For bugs, reproduce the problem yourself and write
  the regression test from scratch before (or while) you fix it.
- Production runs against MongoDB and Redis on several app servers; in this repo those are the
  in-process stand-ins in `nyc_health/db/`. Write the solution as you would for the real thing.
- Some tickets are small fixes, others need a bit of design thinking. Read the whole ticket,
  including the "Operational context" notes.

---

## HN-412 — Doctors are being double-booked
**Type:** Bug  **Priority:** High  **Reporter:** Front Desk Ops (Bellevue)

**Description**
Several front-desk staff at Bellevue have noticed doctors showing two appointments at the same time
on their daily agenda. Dr. Raman had a 30-minute consult at 9:30 AM and then a 2-hour MRI review was
booked starting at 9:00 AM for a different patient. The system accepted both. It does not happen
with every conflicting booking, and the double-booking only seems to happen when a booking is made
after the shorter one already exists.

Facilities also reported something similar when scheduling staff shifts: a nurse ended up with a
short overnight coverage shift "inside" a longer shift she already had.

**Expected behavior**
- No two active appointments for the same doctor may overlap in time, regardless of their relative
  lengths or the order they were booked in.
- The same guarantee applies to a patient's own appointments and to a staff member's shifts.
- Back-to-back appointments (one ends exactly when the next starts) remain allowed.

**Acceptance criteria**
- The reproduction above is rejected with a scheduling conflict error.
- Existing valid bookings (back-to-back, different doctors, cancelled slots reused) still work.
- Regression tests (that you write) cover the failing scenario for appointments and for shifts.

---

## HN-431 — Patients charged the full deductible on every invoice
**Type:** Bug  **Priority:** High  **Reporter:** Patient Billing Team

**Description**
Billing has received multiple complaints from insured patients. A patient with a $1,500 annual
deductible had two $1,200 MRI invoices finalized in the same week. Both invoices show the patient
owing the full $1,200, as though none of the deductible had been used up by the first one. The
patient should owe $1,200 on the first invoice and only $300 (deductible) plus the usual copay and
coinsurance on the second.

Finance also noted that when an invoice is voided after it was finalized, the deductible credit
that invoice consumed should go back to the patient, but there is currently no way to get that
credit back.

**Expected behavior**
- Deductible consumed by a finalized invoice counts toward later invoices for the same patient
  within the policy.
- Voiding a finalized, unpaid invoice restores the deductible amount it consumed.
- Invoices with no insurance, or with an expired policy, continue to be billed at full price.
- Finalizing the same invoice twice must not consume the deductible twice.

**Acceptance criteria**
- Reproduction scenario produces $1,200 then $300 + copay/coinsurance.
- Voiding a finalized invoice restores the policy's remaining deductible; voiding a draft changes nothing.
- Tests added for the multi-invoice scenario and the void scenario.

---

## HN-447 — Appointment waitlist
**Type:** Feature  **Priority:** Medium  **Reporter:** Patient Access Team

**Description**
Popular specialists (especially cardiology at Bellevue) fill up weeks in advance, and when someone
cancels, the slot usually goes unused. We want patients to be able to join a waitlist for a doctor
on a given day and be offered cancelled slots automatically.

**Requirements**
- A patient can join the waitlist for a specific doctor and date, with a desired duration (a multiple
  of the standard slot length).
- A patient can leave the waitlist. A patient cannot be on the same doctor/date waitlist twice, and
  cannot join for a date in the past.
- When an appointment for that doctor on that date is cancelled, the system finds the first
  waitlisted patient (oldest request first) whose desired duration fits into the freed time and who
  has no conflicting appointment of their own. That patient is automatically booked into the freed
  slot and notified (through their preferred channel) that they have been booked off the waitlist.
- Patients that were skipped (their request does not fit or conflicts) stay on the waitlist.
- A patient who is promoted is removed from the waitlist.
- Cancellation must still succeed even if nobody can be promoted.

**Operational context**
- During flu season the Bellevue cardiology waitlist can hold tens of thousands of entries across
  all doctors and dates, and a clinic closing early can cancel dozens of appointments within seconds.
  Handling one cancellation must only look at the waitlist entries for that doctor and date.
- Cancellation events are delivered **at least once**: the same cancellation can be processed twice,
  and it can be processed by two app servers at the same moment. It must never promote two patients
  into one slot or send the same patient two "you're booked" messages.

**Acceptance criteria**
- Waitlist behavior is covered by tests (join, leave, duplicate join, promotion order, skip rules,
  nobody eligible, duplicate/redelivered cancellation).
- Handling a cancellation does not scan the whole waitlist.
- Existing cancellation and notification behavior is unchanged for doctors without a waitlist.

---

## HN-455 — Transfer admitted patients between wards
**Type:** Feature  **Priority:** Medium  **Reporter:** Bed Management

**Description**
Today a patient stays in the bed they were first admitted to. Nursing supervisors need to move
patients between wards (for example General -> ICU when a patient deteriorates, or General ->
Isolation after a positive test) and need an audit trail of every move.

**Requirements**
- Add the ability to transfer a currently admitted patient to a different ward in the same hospital,
  with a required reason.
- The old bed becomes free and the patient is assigned the first free bed in the target ward.
- If the target ward has no free beds, the transfer fails and the patient stays in their current bed
  with nothing changed.
- Infectious patients may only be transferred into an isolation ward. A patient may not be
  transferred to the ward they are already in.
- Every transfer is recorded (from bed, to bed, reason, timestamp) and the history of a patient's
  transfers during an admission can be retrieved in chronological order.
- A `patient.transferred` event is published after a successful transfer.
- Transfers of discharged admissions are not allowed.

**Operational context**
- Several supervisors, on different app servers, work the same wards at once. When the ICU has a
  single free bed and two supervisors submit transfers for two different patients at the same moment,
  exactly one must get the bed; the other must fail cleanly and stay where they are. A bed must never
  end up assigned to two admissions.
- Every nurse station polls the ward occupancy view every few seconds, so it has to stay cheap -
  but it must never show numbers that are out of date after a transfer.

**Acceptance criteria**
- New behavior is covered by tests, including failure paths that must leave occupancy untouched and
  the "last free bed" race.
- Occupancy reports remain correct after transfers.
- Existing admit/discharge behavior is unchanged.
