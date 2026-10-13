from datetime import date, datetime

import pytest

from nyc_health.core.clock import FrozenClock
from nyc_health.db import DuplicateKeyError, FakeMongoDatabase, FakeRedis, codec
from nyc_health.models.appointment import Appointment, AppointmentStatus
from nyc_health.models.hospital import Hospital
from nyc_health.models.bed import WardType
from nyc_health.models.patient import Borough


@pytest.fixture
def db():
    return FakeMongoDatabase()


@pytest.fixture
def col(db):
    return db["things"]


class TestFakeMongo:
    def test_insert_and_find_one_round_trip_is_a_copy(self, col):
        col.insert_one({"_id": "a", "tags": ["x"]})
        doc = col.find_one({"_id": "a"})
        doc["tags"].append("y")
        assert col.find_one({"_id": "a"})["tags"] == ["x"]

    def test_duplicate_id_rejected(self, col):
        col.insert_one({"_id": "a"})
        with pytest.raises(DuplicateKeyError):
            col.insert_one({"_id": "a"})

    def test_comparison_operators(self, col):
        for i in range(5):
            col.insert_one({"_id": str(i), "n": i})
        assert [d["n"] for d in col.find({"n": {"$gte": 1, "$lt": 4}}, sort=[("n", 1)])] == [1, 2, 3]
        assert [d["n"] for d in col.find({"n": {"$in": [0, 4]}}, sort=[("n", -1)])] == [4, 0]
        assert col.count_documents({"n": {"$ne": 2}}) == 4

    def test_sort_and_limit(self, col):
        for i in (3, 1, 2):
            col.insert_one({"_id": str(i), "n": i})
        assert [d["n"] for d in col.find({}, sort=[("n", 1)], limit=2)] == [1, 2]

    def test_update_operators(self, col):
        col.insert_one({"_id": "a", "n": 1, "gone": True})
        assert col.update_one({"_id": "a"}, {"$set": {"s": "x"}, "$inc": {"n": 4}, "$unset": {"gone": ""}})
        assert col.find_one({"_id": "a"}) == {"_id": "a", "n": 5, "s": "x"}
        assert not col.update_one({"_id": "missing"}, {"$set": {"n": 1}})

    def test_find_one_and_update_claims_once(self, col):
        col.insert_one({"_id": "bed", "owner": None})
        first = col.find_one_and_update({"_id": "bed", "owner": None}, {"$set": {"owner": "A"}})
        second = col.find_one_and_update({"_id": "bed", "owner": None}, {"$set": {"owner": "B"}})
        assert first["owner"] == "A" and second is None

    def test_unique_index(self, col):
        col.create_index(["email"], unique=True)
        col.insert_one({"_id": "1", "email": "a@x.com"})
        with pytest.raises(DuplicateKeyError):
            col.insert_one({"_id": "2", "email": "a@x.com"})

    def test_index_avoids_full_scan(self, db, col):
        col.create_index(["group"])
        for i in range(100):
            col.insert_one({"_id": str(i), "group": i % 10})
        db.reset_stats()
        assert len(col.find({"group": 3})) == 10
        assert db.stats.docs_examined == 10 and db.stats.full_scans == 0

    def test_unindexed_query_scans_everything(self, db, col):
        for i in range(20):
            col.insert_one({"_id": str(i), "group": i % 4})
        db.reset_stats()
        col.find({"group": 1})
        assert db.stats.docs_examined == 20 and db.stats.full_scans == 1


class TestFakeRedis:
    def test_ttl_expiry_uses_clock(self):
        clock = FrozenClock(datetime(2026, 3, 2, 7, 0))
        redis = FakeRedis(clock)
        redis.setex("k", 30, "v")
        assert redis.get("k") == "v" and redis.ttl("k") == 30
        clock.advance(seconds=31)
        assert redis.get("k") is None and redis.ttl("k") == -2

    def test_set_nx(self):
        redis = FakeRedis(FrozenClock(datetime(2026, 3, 2, 7, 0)))
        assert redis.set("lock", "1", nx=True) is True
        assert redis.set("lock", "2", nx=True) is False
        assert redis.get("lock") == "1"

    def test_incr_keys_and_delete(self):
        redis = FakeRedis(FrozenClock(datetime(2026, 3, 2, 7, 0)))
        assert redis.incr("hits") == 1 and redis.incr("hits", 4) == 5
        redis.set("patient:1", "a")
        redis.set("patient:2", "b")
        assert redis.keys("patient:*") == ["patient:1", "patient:2"]
        assert redis.delete("patient:1", "nope") == 1


class TestCodec:
    def test_dataclass_round_trip_with_enums_and_datetimes(self):
        appt = Appointment("APT-1", "PAT-1", "STF-1", "H-1", datetime(2026, 3, 3, 9), 30, "CONSULT",
                           datetime(2026, 3, 2, 7), AppointmentStatus.CHECKED_IN)
        assert codec.from_document(Appointment, codec.to_document(appt)) == appt

    def test_json_round_trip_for_cache_values(self):
        from nyc_health.models.patient import Patient
        patient = Patient("PAT-1", "A", "B", date(1990, 1, 2), "+17185550100", Borough.QUEENS)
        assert codec.loads(Patient, codec.dumps(patient)) == patient

    def test_dict_with_enum_keys(self):
        hospital = Hospital("H-1", "Test", Borough.BRONX, {WardType.ICU: 2})
        assert codec.from_document(Hospital, codec.to_document(hospital)) == hospital
