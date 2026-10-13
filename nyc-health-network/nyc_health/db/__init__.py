"""Cheap in-process stand-ins for MongoDB and Redis (see README, "Data layer")."""
from nyc_health.db.mongo import DuplicateKeyError, FakeCollection, FakeMongoDatabase
from nyc_health.db.redis import FakeRedis

__all__ = ["DuplicateKeyError", "FakeCollection", "FakeMongoDatabase", "FakeRedis"]
