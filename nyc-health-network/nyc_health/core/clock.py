"""Injectable clock so services never call datetime.now() directly."""
from datetime import datetime, timedelta


class Clock:
    def now(self) -> datetime:
        return datetime.now().replace(microsecond=0)


class FrozenClock(Clock):
    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment

    def advance(self, **kwargs) -> None:
        self._moment += timedelta(**kwargs)

    def set(self, moment: datetime) -> None:
        self._moment = moment
