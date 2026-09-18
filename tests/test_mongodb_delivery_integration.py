"""Integration coverage for the MongoDB-backed delivery claim."""

from concurrent.futures import ThreadPoolExecutor
import os
from uuid import uuid4

import pytest

from Integration.mongodb_handler import MongoDBHandler


@pytest.mark.integration
def test_delivery_claim_is_atomic_against_mongodb():
    """A unique delivery index must allow exactly one concurrent claimant."""
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        pytest.skip("MONGODB_URI is required for the MongoDB integration test")

    database = f"immo_ci_delivery_{uuid4().hex}"
    handlers = [
        MongoDBHandler(uri=uri, db_name=database),
        MongoDBHandler(uri=uri, db_name=database),
    ]
    alert_id = f"ci-alert-{uuid4().hex}"
    url_hash = "ci-delivery-key"

    try:
        assert all(handler.ensure_delivery_index() for handler in handlers)

        def claim(handler: MongoDBHandler) -> bool:
            return handler.claim_delivery(
                alert_id,
                url_hash,
                chat_id="-1000000000000",
                message="CI integration claim",
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            claims = list(executor.map(claim, handlers))

        assert sorted(claims) == [False, True]
        rows = list(
            handlers[0].db["alert_deliveries"].find({"alert_id": alert_id})
        )
        assert len(rows) == 1
        assert rows[0]["url_hash"] == url_hash
    finally:
        for handler in handlers:
            if handler.client is not None:
                handler.client.drop_database(database)
            handler.close()


@pytest.mark.integration
def test_delivery_claim_handles_legacy_alias_upsert_against_mongodb():
    """The migration alias filter must both suppress and insert safely."""
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        pytest.skip("MONGODB_URI is required for the MongoDB integration test")

    database = f"immo_ci_delivery_alias_{uuid4().hex}"
    handler = MongoDBHandler(uri=uri, db_name=database)
    legacy_alert_id = f"ci-legacy-alert-{uuid4().hex}"
    new_alert_id = f"ci-new-alert-{uuid4().hex}"
    fingerprint = f"ci-fingerprint-{uuid4().hex}"
    legacy_hash = f"ci-legacy-hash-{uuid4().hex}"

    try:
        assert handler.ensure_delivery_index()
        deliveries = handler.db["alert_deliveries"]
        deliveries.insert_one({
            "alert_id": legacy_alert_id,
            "url_hash": legacy_hash,
            "status": "sent",
        })

        assert handler.claim_delivery(
            legacy_alert_id,
            fingerprint,
            delivery_fingerprint=fingerprint,
            legacy_delivery_url_hash=legacy_hash,
        ) is False
        assert deliveries.count_documents({"alert_id": legacy_alert_id}) == 1

        assert handler.claim_delivery(
            new_alert_id,
            fingerprint,
            delivery_fingerprint=fingerprint,
            legacy_delivery_url_hash=legacy_hash,
        ) is True
        row = deliveries.find_one({"alert_id": new_alert_id}, {"_id": 0})
        assert row["url_hash"] == fingerprint
    finally:
        if handler.client is not None:
            handler.client.drop_database(database)
        handler.close()
