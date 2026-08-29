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
