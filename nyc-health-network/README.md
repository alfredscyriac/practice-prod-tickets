# NYC Health Network — Backend

Python service layer for a (fictional) network of NYC public hospitals: patient registration,
doctor scheduling, appointment booking, inpatient bed management, insurance claims and billing.

## Getting started

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Conventions

- Python 3.10+, standard library only (plus pytest).
- Money is **integer cents**. Never use floats for currency.
- Datetimes are naive and represent America/New_York local time. Use the injected `Clock`, never `datetime.now()`.
- Layering: `api/` -> `services/` -> `repositories/` -> `models/`. Services talk to each other
  directly or through the `EventBus`. `container.py` is the composition root.
- Domain errors live in `exceptions.py`; handlers translate them into HTTP-style status codes.
- Every behavior change should come with tests in `tests/`.
