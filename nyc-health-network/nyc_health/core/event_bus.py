"""Tiny synchronous pub/sub used to decouple services (notifications, reporting, ...)."""
from collections import defaultdict
from typing import Any, Callable, Dict, List, Tuple

Handler = Callable[[Dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: Dict[str, List[Handler]] = defaultdict(list)
        self.history: List[Tuple[str, Dict[str, Any]]] = []

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._handlers[event_name].append(handler)

    def publish(self, event_name: str, payload: Dict[str, Any]) -> None:
        self.history.append((event_name, dict(payload)))
        for handler in list(self._handlers.get(event_name, [])):
            handler(payload)

    def events_named(self, event_name: str) -> List[Dict[str, Any]]:
        return [payload for name, payload in self.history if name == event_name]
