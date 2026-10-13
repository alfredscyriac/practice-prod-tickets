# AI-Assisted Codebase Interview Prep

Practice repos that simulate the "AI-assisted codebase interview": you get a production-sized Python
repository and a set of production-style tickets, complete **one** with an AI assistant, and are
judged on how well you narrow scope, verify, and ship.

## What's in here

| Path | What it is |
| --- | --- |
| `GENERATE_INTERVIEW_REPO_PROMPT.md` | Prompt that makes Claude Code generate a *new* practice repo (new domain) |
| `nyc-health-network/` | Example practice repo: hospital network (scheduling, billing, beds) on fake MongoDB + Redis |
| `<future-repo>/` | Each repo has its own `README.md`, `TICKETS.md` and `ANSWER_KEY.md` |

Each practice repo contains:

- `README.md` — how to run it, layout, conventions, how the fake database/cache work
- `TICKETS.md` — the tickets you work from (this is all the AI should be given besides the code)
- `ANSWER_KEY.md` — root causes, scope, design points. **Do not read before attempting.**
- `nyc_health/`-style package (`api/ services/ repositories/ models/ db/ core/ utils/`) and a green `tests/` suite

## How to practice

1. **Set up.** `cd nyc-health-network`, create a venv, `pip install -r requirements.txt`, run `pytest`
   (everything must pass; there is deliberately no failing test pointing at the bugs).
2. **Start the clock.** Time-box to 45–60 minutes, like the real thing.
3. **Pick one ticket** from `TICKETS.md`. Open your AI assistant (e.g. Claude Code) *in the repo*
   and give it only that ticket (plus the README if you like). Do not paste the answer key.
4. **Work the way you would in the interview:**
   - Ask the AI to find the relevant files first; check its scope yourself.
   - For bugs: reproduce first and write the failing test from scratch, then fix.
   - For features/design tickets: decide the data model, indexes, atomicity and cache/idempotency
     strategy *before* coding; say why.
   - Run the full `pytest` suite at the end — everything must pass.
5. **Review.** Open `ANSWER_KEY.md` and compare: did you pick the right files, find the true root
   cause, handle the listed gotchas and design points, and avoid the distractors?
6. **Reset to retry.** `git restore . && git clean -fd -- <repo>` puts the repo back to the start
   (careful: this discards your work), then try a different ticket.

## Ticket mix

Each repo ships 4 tickets: typically 2 root-cause bugs and 2 feature tickets, with roughly half
needing system-design thinking (indexed lookups instead of scans, idempotent event handling,
atomic claims instead of check-then-act, cache invalidation).

## Making another repo

Open Claude Code in this folder and say: *"follow GENERATE_INTERVIEW_REPO_PROMPT.md"*. It will ask
for a domain (it picks one not already present), then generate the repo with its own README, tickets
and answer key, using the same fake MongoDB/Redis layer.
