"""Converts dataclass models to/from Mongo-style documents (and JSON-able dicts for cache values).

Enums are stored by value, `date` as an ISO string, `datetime` natively (Mongo has a datetime type),
nested dataclasses as sub-documents. Decoding walks the dataclass type hints.
"""
import json
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, Type, TypeVar, Union, get_args, get_origin, get_type_hints

T = TypeVar("T")


def to_document(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_document(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, (list, tuple, set)):
        return [to_document(v) for v in obj]
    if isinstance(obj, dict):
        return {(k.value if isinstance(k, Enum) else k): to_document(v) for k, v in obj.items()}
    return obj


def from_document(cls: Type[T], doc: Dict[str, Any]) -> T:
    hints = get_type_hints(cls)
    kwargs = {f.name: _decode(hints[f.name], doc[f.name]) for f in fields(cls) if f.name in doc}
    return cls(**kwargs)


def _decode(tp: Any, value: Any) -> Any:
    if value is None:
        return None
    origin = get_origin(tp)
    if origin is Union:
        inner = [a for a in get_args(tp) if a is not type(None)]
        return _decode(inner[0], value)
    if origin in (list, set, tuple):
        (item_type,) = get_args(tp) or (Any,)
        items = [_decode(item_type, v) for v in value]
        return origin(items) if origin is not list else items
    if origin is dict:
        key_type, val_type = get_args(tp)
        return {_decode(key_type, k): _decode(val_type, v) for k, v in value.items()}
    if isinstance(tp, type):
        if is_dataclass(tp):
            return from_document(tp, value)
        if issubclass(tp, Enum):
            return tp(value)
        if tp is datetime:
            return value if isinstance(value, datetime) else datetime.fromisoformat(value)
        if tp is date:
            return date.fromisoformat(value)
    return value


def dumps(obj: Any) -> str:
    """Serialize a model (or list of models) for a cache value."""
    return json.dumps(to_document(obj), default=lambda o: {"__dt__": o.isoformat()} if isinstance(o, datetime) else str(o))


def loads(cls: Type[T], text: str) -> T:
    return from_document(cls, json.loads(text, object_hook=_revive))


def _revive(obj: Dict[str, Any]) -> Any:
    if set(obj) == {"__dt__"}:
        return datetime.fromisoformat(obj["__dt__"])
    return obj
