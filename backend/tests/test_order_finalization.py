import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import server


class FakeOrdersCollection:
    def __init__(self, document):
        self.document = document

    async def update_one(self, query, update):
        doc = self.document

        if doc is None or doc["order_id"] != query["order_id"]:
            return SimpleNamespace(modified_count=0)

        if doc.get("shopify_order_id") not in query["shopify_order_id"]["$in"]:
            return SimpleNamespace(modified_count=0)

        allowed_statuses = query["$or"]

        status = doc.get("shopify_sync_status")
        eligible = (
            status in allowed_statuses[0]["shopify_sync_status"]["$in"]
            or (
                status == "processing"
                and doc.get("shopify_sync_lease_until")
                <= query["$or"][1]["shopify_sync_lease_until"]["$lte"]
            )
        )

        if not eligible:
            return SimpleNamespace(modified_count=0)

        doc.update(update["$set"])
        return SimpleNamespace(modified_count=1)


def run_claim(order_id):
    return asyncio.run(server._claim_shopify_sync(order_id))


@pytest.fixture
def claim_collection(monkeypatch):
    now = datetime.now(timezone.utc)

    document = {
        "order_id": "MSR-TEST1234",
        "shopify_order_id": None,
        "shopify_sync_status": None,
        "shopify_sync_lease_until": None,
    }

    collection = FakeOrdersCollection(document)

    monkeypatch.setattr(
        server,
        "db",
        SimpleNamespace(orders=collection),
    )

    return collection


def test_claim_succeeds_for_new_order(claim_collection):
    token = run_claim("MSR-TEST1234")

    assert token is not None
    assert isinstance(token, str)
    assert claim_collection.document["shopify_sync_status"] == "processing"
    assert claim_collection.document["shopify_sync_token"] == token
    assert claim_collection.document["shopify_sync_lease_until"] is not None


def test_claim_fails_for_wrong_order_id(claim_collection):
    token = run_claim("MSR-UNKNOWN")

    assert token is None


def test_claim_fails_when_shopify_order_already_exists(claim_collection):
    claim_collection.document["shopify_order_id"] = "gid://shopify/Order/123"

    token = run_claim("MSR-TEST1234")

    assert token is None


def test_claim_fails_when_another_sync_is_processing(claim_collection):
    claim_collection.document["shopify_sync_status"] = "processing"
    claim_collection.document["shopify_sync_lease_until"] = (
        datetime.now(timezone.utc) + timedelta(minutes=5)
    )

    token = run_claim("MSR-TEST1234")

    assert token is None


def test_claim_succeeds_when_previous_lease_expired(claim_collection):
    claim_collection.document["shopify_sync_status"] = "processing"
    claim_collection.document["shopify_sync_lease_until"] = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    )

    token = run_claim("MSR-TEST1234")

    assert token is not None
    assert claim_collection.document["shopify_sync_token"] == token


def test_claim_succeeds_after_previous_failure(claim_collection):
    claim_collection.document["shopify_sync_status"] = "failed"

    token = run_claim("MSR-TEST1234")

    assert token is not None
    assert claim_collection.document["shopify_sync_status"] == "processing"


def test_claim_generates_unique_tokens(claim_collection):
    first = run_claim("MSR-TEST1234")

    # Simulate the previous claim being released after a failure.
    claim_collection.document["shopify_sync_status"] = "failed"

    second = run_claim("MSR-TEST1234")

    assert first is not None
    assert second is not None
    assert first != second

# -------------------------------------------------------------------
# _finalize_paid_order tests — isolated mocks, no live services
# -------------------------------------------------------------------

class FakeFinalizationOrdersCollection:
    def __init__(self):
        self.documents = {}

    async def find_one(self, query, projection=None):
        doc = self.documents.get(query["order_id"])
        return dict(doc) if doc else None

    async def insert_one(self, document):
        order_id = document["order_id"]
        if order_id in self.documents:
            raise server.DuplicateKeyError("Duplicate order")
        self.documents[order_id] = dict(document)
        return SimpleNamespace(inserted_id=order_id)

    async def update_one(self, query, update):
        doc = self.documents.get(query["order_id"])
        if doc is None:
            return SimpleNamespace(modified_count=0)

        for key, value in update.get("$set", {}).items():
            doc[key] = value

        for key in update.get("$unset", {}):
            doc.pop(key, None)

        return SimpleNamespace(modified_count=1)


@pytest.fixture
def finalization_setup(monkeypatch):
    collection = FakeFinalizationOrdersCollection()

    monkeypatch.setattr(
        server,
        "db",
        SimpleNamespace(orders=collection),
    )

    async def fake_email(order_doc):
        return True, None

    async def fake_shiprocket(order_doc):
        return {
            "success": True,
            "shiprocket_order_id": "SR-123",
            "shipment_id": "SHIP-123",
            "awb_number": "AWB-123",
            "courier_name": "Test Courier",
        }

    async def fake_shopify(order_doc):
        return {
            "outcome": "success",
            "shopify_order_id": "gid://shopify/Order/123",
            "order_number": "123",
        }

    async def fake_claim(order_id):
        return "test-claim-token"

    monkeypatch.setattr(server, "_send_order_emails", fake_email)
    monkeypatch.setattr(
        server.shiprocket_client,
        "create_adhoc_order",
        fake_shiprocket,
    )
    monkeypatch.setattr(
        server.shopify_client,
        "create_shopify_order",
        fake_shopify,
    )
    monkeypatch.setattr(server, "_claim_shopify_sync", fake_claim)

    txn = {
        "order_id": "MSR-FINAL123",
        "rzp_order_id": "order_test123",
        "rzp_payment_id": "pay_test123",
        "customer_name": "Test Customer",
        "customer_email": "test@example.com",
        "customer_contact": "9999999999",
        "shipping_address": "Test Address, Mumbai",
        "address_struct": {},
        "items": [
            {
                "name": "Test Perfume",
                "slug": "test-perfume",
                "quantity": 1,
                "line_total": 1149.00,
            }
        ],
        "amount": 1149.00,
        "currency": "INR",
    }

    return collection, txn


def test_finalize_paid_order_creates_order_and_syncs_services(
    finalization_setup,
):
    collection, txn = finalization_setup

    result = asyncio.run(
        server._finalize_paid_order(txn, "pay_test123")
    )

    assert result["order_id"] == "MSR-FINAL123"
    assert result["status"] == "paid"
    assert result["currency"] == "INR"

    assert result["confirmation_email_sent"] is True
    assert result["shiprocket_order_id"] == "SR-123"
    assert result["awb_number"] == "AWB-123"
    assert result["shopify_order_id"] == "gid://shopify/Order/123"
    assert result["shopify_sync_status"] == "synced"

    assert "MSR-FINAL123" in collection.documents


def test_shiprocket_exception_does_not_block_shopify_sync(
    finalization_setup,
    monkeypatch,
):
    collection, txn = finalization_setup

    async def failing_shiprocket(order_doc):
        raise RuntimeError("Shiprocket temporarily unavailable")

    monkeypatch.setattr(
        server.shiprocket_client,
        "create_adhoc_order",
        failing_shiprocket,
    )

    result = asyncio.run(
        server._finalize_paid_order(txn, "pay_test123")
    )

    assert result["status"] == "paid"
    assert result["shiprocket_error"] == (
        "Shiprocket temporarily unavailable"
    )
    assert result["shopify_order_id"] == "gid://shopify/Order/123"
    assert result["shopify_sync_status"] == "synced"

    assert collection.documents["MSR-FINAL123"]["status"] == "paid"

def test_email_failure_does_not_block_paid_order(finalization_setup, monkeypatch):
    collection, txn = finalization_setup

    async def failing_email(order_doc):
        return False, "Email service unavailable"

    monkeypatch.setattr(server, "_send_order_emails", failing_email)

    result = asyncio.run(
        server._finalize_paid_order(txn, "pay_test123")
    )

    assert result["status"] == "paid"
    assert result["confirmation_email_sent"] is False
    assert result["confirmation_email_error"] == "Email service unavailable"
    assert result["shopify_order_id"] == "gid://shopify/Order/123"


def test_existing_shopify_order_is_not_processed_again(finalization_setup, monkeypatch):
    collection, txn = finalization_setup

    existing_order = {
        "order_id": txn["order_id"],
        "status": "paid",
        "shopify_order_id": "gid://shopify/Order/existing",
        "shopify_order_number": "OLD-123",
    }
    collection.documents[txn["order_id"]] = existing_order.copy()

    async def should_not_be_called(*args, **kwargs):
        raise AssertionError("External service should not be called")

    monkeypatch.setattr(server, "_send_order_emails", should_not_be_called)
    monkeypatch.setattr(
        server.shiprocket_client,
        "create_adhoc_order",
        should_not_be_called,
    )
    monkeypatch.setattr(
        server.shopify_client,
        "create_shopify_order",
        should_not_be_called,
    )

    result = asyncio.run(
        server._finalize_paid_order(txn, "pay_test123")
    )

    assert result["shopify_order_id"] == "gid://shopify/Order/existing"
    assert result["shopify_order_number"] == "OLD-123"


@pytest.mark.parametrize(
    ("shopify_result", "expected_status"),
    [
        (
            {"outcome": "failed", "error": "Shopify API rejected order"},
            "failed",
        ),
        (
            {"outcome": "unknown", "error": "Could not confirm Shopify result"},
            "unknown",
        ),
    ],
)
def test_shopify_failure_outcomes_are_recorded(
    finalization_setup,
    monkeypatch,
    shopify_result,
    expected_status,
):
    collection, txn = finalization_setup

    async def fake_shopify(order_doc):
        return shopify_result

    monkeypatch.setattr(
        server.shopify_client,
        "create_shopify_order",
        fake_shopify,
    )

    result = asyncio.run(
        server._finalize_paid_order(txn, "pay_test123")
    )

    assert result["status"] == "paid"
    assert result["shopify_sync_status"] == expected_status
    assert result["shopify_error"] == shopify_result["error"]
    assert result.get("shopify_order_id") is None