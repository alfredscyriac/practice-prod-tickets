# NYC Health Network — Backend

Python service layer for a (fictional) network of NYC public hospitals: patient registration,
doctor scheduling, appointment booking, inpatient bed management, insurance claims and billing.
Persistence is a fake MongoDB, with a fake Redis cache in front of some reads.

## Getting started

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest            # must be green before you start
```

Then read [TICKETS.md](TICKETS.md) and complete one ticket. [ANSWER_KEY.md](ANSWER_KEY.md) is for
checking your work afterwards — don't open it first.

## Layout

```
nyc_health/
  api/            thin request handlers (dict in -> (status, dict) out)
  services/       business rules: scheduling, shifts, patients, billing, insurance, beds, notifications, reporting
  repositories/   one class per collection, built on MongoRepository
  models/         dataclasses + enums + state machines
  db/             FakeMongoDatabase, FakeRedis, codec (model <-> document)
  core/           injectable Clock, synchronous EventBus
  utils/          time, money, validators, id generation
  container.py    composition root (build_container)
  seed.py         demo data
tests/            pytest suite, shared fixtures in conftest.py
```

## Data layer

Production uses MongoDB and Redis; here they are in-process stand-ins with the same shape.

- **`db/mongo.py` — `FakeMongoDatabase`**: `db["appointments"]` returns a collection with
  `insert_one`, `find_one`, `find(filter, sort, limit)`, `update_one`, `replace_one`,
  `find_one_and_update` (atomic), `delete_one`, `count_documents`, `create_index(fields, unique=)`.
  Filters support equality plus `$eq $ne $gt $gte $lt $lte $in $nin`; updates support `$set $inc $unset`.
- **Copies, not references.** Documents are copied on the way in and out, so an entity you load is
  a copy: changes are lost until you call `repo.update(entity)`.
- **Indexes matter.** Repositories declare `indexes`; a query whose filter has equality on every
  field of an index is an index hit, anything else is a full scan. `container.db.stats`
  (`queries`, `docs_examined`, `index_hits`, `full_scans`; `container.db.reset_stats()`) lets a test
  assert a query stayed cheap. `repo.find(predicate)` loads *everything*; `repo.find_where(filter)` runs
  in the database.
- **`db/redis.py` — `FakeRedis`**: `get`, `set(key, value, ex=, nx=)`, `setex`, `delete`, `exists`,
  `incr`, `expire`, `ttl`, `keys`. Values are strings. Expiry follows the injected clock, so tests
  advance `FrozenClock` to expire keys.
- **Currently cached** (cache-aside, invalidated on write): `patient:{id}` (`PatientService.get`) and
  `occupancy:{hospital_id}` (`BedService.occupancy`).
- **Concurrency model**: the fakes are thread-safe per operation (one lock), just as individual Mongo/Redis
  commands are atomic; a sequence of calls is *not* atomic. Think about check-then-act races the way
  you would with the real services, and use `find_one_and_update` / `set(nx=True)` where it matters.

## Conventions

- Python 3.10+, standard library only (plus pytest).
- Money is **integer cents**. Never use floats for currency.
- Datetimes are naive and represent America/New_York local time. Use the injected `Clock`, never `datetime.now()`.
- Layering: `api/` -> `services/` -> `repositories/` -> `models/`. Services talk to each other
  directly or through the `EventBus`. `container.py` is the composition root.
- Domain errors live in `exceptions.py`; handlers translate them into HTTP-style status codes.
- Every behavior change should come with tests in `tests/`.
