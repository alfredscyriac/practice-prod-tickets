# Prompt: Generate an AI-Assisted Codebase Interview Practice Repo

How to use: open Claude Code in `ai-coding-interview-prep/`, then paste everything below the line
(or say "follow GENERATE_INTERVIEW_REPO_PROMPT.md"). Optionally prefill answers to the questions
in Step 1 so it skips asking. Reference example: `nyc-health-network/` (copy its `db/` package and `MongoRepository` seam).

---

## Context

I'm preparing for an AI-assisted codebase interview. In the real interview I get a production-sized
Python repository plus 4 production-style tickets and must complete ONE, using an AI assistant.
Build me a practice repo and ticket set that simulates this as closely as possible.

## Step 1: Ask me questions BEFORE generating anything

Use the question tool (up to 4 questions per round) to confirm:
1. Domain (NYC-inspired: subway, taxi/TLC, schools, hospital, courts, libraries, housing, etc.).Pick a different domain from existing folders in this directory.
2. Scale: medium (~20-30 source files, ~2-4k lines), large (40+).
3. Ticket mix: bug fix, new feature, refactor, performance/edge cases, security, migration, etc.
4. Stack: pure Python + pytest (default)
5. Anything else: difficulty level, languages other than Python, "ticket vagueness", whether
   some tests should already be failing.

## Step 2: Build the repo (new folder in this directory)

Requirements:
- Layered architecture, e.g. `api/ -> services/ -> repositories/ -> models/`, plus `utils/`, `core/`
  (injectable clock, event bus), `config.py`, `exceptions.py`, `container.py` (composition root),
  `seed.py`, `pyproject.toml`, `requirements.txt`, `README.md` (with conventions), `.gitignore`.
- Substance in every file: dataclasses/enums/state machines, classes with constructors and real
  methods, validation, domain rules. No stub files. Money in integer cents, injected clock.
- Tests for every layer in `tests/` with a shared `conftest.py` (fixtures, frozen clock).
  The suite must be GREEN at the start. Run `pytest` and confirm before finishing. Tests must
  not already cover the ticket bugs' failing scenarios, and there must be NO failing/skipped/xfail
  test hinting at a ticket: the candidate writes the reproducing test from scratch. Keep the rest of
  the suite full (every layer, including the db package and the caches).
- **Fake database + cache** (the real interview uses MongoDB and Redis). Copy the pattern from
  `nyc-health-network/nyc_health/db/` into the new repo: a `FakeMongoDatabase` (pymongo-style
  collections: insert/find/update/replace/`find_one_and_update`/delete/count, `$`-operators, equality
  indexes incl. unique, deep-copy on read/write, a `stats` object counting docs examined / index hits /
  full scans), a `FakeRedis` (get/set with `ex`/`nx`, setex, delete, incr, expire, ttl, keys; TTL driven by
  the injected clock), and a `codec` for dataclass <-> document. Repositories subclass a `MongoRepository`
  base (`model`, `collection_name`, `indexes`, `find_where` for DB-side filters). Wire both through
  `container.py`, and use Redis for at least two real cache-aside reads that are invalidated on write.
  Entities returned by repositories are copies, so services must call `update()`.
- Include realistic distractor modules that are NOT relevant to any ticket (reporting, notifications,
  seed data, API handlers) so I must narrow scope, not read everything.
- Services communicate directly and via an event bus so features have realistic integration points.

## Step 3: Design the tickets (default 4; mix per my answers)

- Each ticket's real scope is a SMALL subset (about 4-6 files) of the repo.
- Tickets must NOT name files, functions, or root causes. Describe symptoms/business behavior only,
  the way a PM, support team, or ops team would write them. Bugs include a realistic repro story.
- Each ticket has: ID, title, type, priority, reporter, description, expected behavior / requirements,
  acceptance criteria. TICKETS.md also states that no failing test is provided and the candidate must
  write regression tests from scratch.
- **System-design tickets**: make about half of the tickets (e.g. 2 of 4) require system-design
  thinking to solve *well*, expressed as business/operational context rather than instructions
  (e.g. "can hold tens of thousands of entries", "events are delivered at least once", "several
  app servers act at the same moment", "this view is polled every few seconds"). Rotate through:
  indexed lookups instead of full scans (assertable via `db.stats`), idempotent/duplicate event handling
  (Redis `SET NX`, unique index), atomic claim instead of check-then-act (`find_one_and_update`),
  cache-aside invalidation, TTL/expiry, rate limiting or pagination. The other tickets can be plain bugs
  or features. Never name the technique in the ticket; put it in the answer key.
- Bugs must be hidden in code paths that the existing tests do NOT cover (so the suite stays green),
  be real root-cause bugs (off-by-one, missing persistence, incorrect overlap logic, wrong order of
  operations), and ideally have a second-order effect elsewhere (a shared helper used by 2+ callers,
  or a missing inverse operation like void/rollback).
- Features must integrate with at least 2-3 existing modules (event bus, notifications, repos,
  container wiring) and include tricky edge cases (atomicity, idempotency, lead-time rules,
  duplicate events, recursion).
- VERIFY every bug actually reproduces by running a small script, and confirm each feature is
  genuinely absent.

## Step 4: Deliverables

0. The root `README.md` of this folder explains how to use the repos; add the new repo to its table.
1. `<repo>/TICKETS.md`: the tickets, with instructions: "Complete ONE; add/update tests; the
   full suite must still pass."
2. `<repo>/ANSWER_KEY.md`: root cause, files in scope, distractors, gotchas and (for system-design
   tickets) the expected design points per ticket,
   labeled "do NOT read before attempting".
3. `<repo>/README.md`: run instructions, layout, the data-layer section (fake Mongo/Redis semantics,
   indexes, copies-not-references, what is cached), and conventions.
4. Final summary message: structure overview, file/line counts, test result, ticket table, and
   practice advice (time-box 45-60 min, give the AI only TICKETS.md plus one ticket, then compare
   its file selection against the answer key).

## Quality bar

- Looks like a real production codebase: consistent naming, docstrings where useful, no TODO stubs.
- Tests pass; bugs reproduce; features absent; tickets don't leak the solution.
- Keep the repo self-contained (stdlib + pytest unless I chose a framework).
