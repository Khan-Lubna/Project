import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import server


class FakePaymentTransactions:
    def __init__(self, document):
        self.document = document.copy()
        self.update_calls = []

    async def find_one(self, query, projection=None):
        for key, value in query.items():
            if key not in self.document:
                return None
            if self.document[key] != value:
                return None
        return self.document.copy()

    async def update_one(self, query, update):
        self.update_calls.append((query, update))

        for key, value in query.items():
            if isinstance(value, dict) and "$ne" in value:
                if self.document.get(key) == value["$ne"]:
                    return
            elif self.document.get(key) != value:
                return

        self.document.update(update.get("$set", {}))


@pytest.fixture
def webhook_mocks(monkeypatch):
    txn = {
        "order_id": "test-order-123",
        "rzp_order_id": "rzp-order-123",
        "rzp_payment_link_id": "plink-123",
        "rzp_payment_id": None,
        "amount_minor": 114900,
        "currency": "INR",
        "payment_status": "initiated",
        "status": "pending",
    }

    transactions = FakePaymentTransactions(txn)
    finalize = AsyncMock()

    monkeypatch.setattr(
        server,
        "db",
        SimpleNamespace(payment_transactions=transactions),
    )
    monkeypatch.setattr(
        server,
        "RAZORPAY_WEBHOOK_SECRET",
        "mock-webhook-secret",
    )
    monkeypatch.setattr(
        server,
        "_verify_signature",
        lambda body, signature, secret: True,
    )
    monkeypatch.setattr(
        server,
        "_finalize_paid_order",
        finalize,
    )

    return SimpleNamespace(
        transactions=transactions,
        finalize=finalize,
    )


def make_request(payload, signature="valid-mock-signature"):
    body = json.dumps(payload).encode("utf-8")

    async def receive():
        return {
            "type": "http.request",
            "body": body,
            "more_body": False,
        }

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/webhook/razorpay",
        "raw_path": b"/webhook/razorpay",
        "query_string": b"",
        "headers": [
            (
                b"x-razorpay-signature",
                signature.encode("utf-8"),
            )
        ],
        "server": ("testserver", 80),
        "client": ("testclient", 123),
    }

    return Request(scope, receive)


def run_webhook(payload, signature="valid-mock-signature"):
    request = make_request(payload, signature)
    return asyncio.run(server.razorpay_webhook(request))


def captured_payload(amount=114900, currency="INR"):
    return {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay-123",
                    "order_id": "rzp-order-123",
                    "amount": amount,
                    "currency": currency,
                    "status": "captured",
                }
            }
        },
    }


def test_captured_payment_marks_transaction_paid(webhook_mocks):
    response = run_webhook(captured_payload())

    txn = webhook_mocks.transactions.document

    assert response == {"received": True}
    assert txn["payment_status"] == "paid"
    assert txn["status"] == "complete"
    assert txn["rzp_payment_id"] == "pay-123"
    webhook_mocks.finalize.assert_awaited_once()


def test_captured_payment_rejects_amount_mismatch(webhook_mocks):
    with pytest.raises(HTTPException) as exc:
        run_webhook(captured_payload(amount=100))

    assert exc.value.status_code == 400
    assert webhook_mocks.transactions.document["payment_status"] == "initiated"
    webhook_mocks.finalize.assert_not_called()


def test_failed_event_does_not_downgrade_paid_transaction(
    webhook_mocks,
):
    webhook_mocks.transactions.document["payment_status"] = "paid"
    webhook_mocks.transactions.document["status"] = "complete"

    payload = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay-123",
                    "order_id": "rzp-order-123",
                    "status": "failed",
                }
            }
        },
    }

    response = run_webhook(payload)

    assert response == {"received": True}
    assert webhook_mocks.transactions.document["payment_status"] == "paid"
    assert webhook_mocks.transactions.document["status"] == "complete"
    webhook_mocks.finalize.assert_not_called()


def test_payment_link_paid_validates_amount_and_finalizes(
    webhook_mocks,
):
    payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": "plink-123",
                    "amount_paid": 114900,
                    "currency": "INR",
                    "payments": [
                        {"payment_id": "pay-link-123"}
                    ],
                }
            }
        },
    }

    response = run_webhook(payload)

    txn = webhook_mocks.transactions.document

    assert response == {"received": True}
    assert txn["payment_status"] == "paid"
    assert txn["status"] == "complete"
    assert txn["rzp_payment_id"] == "pay-link-123"
    webhook_mocks.finalize.assert_awaited_once()


def test_invalid_webhook_signature_is_rejected(
    webhook_mocks, monkeypatch
):
    monkeypatch.setattr(
        server,
        "_verify_signature",
        lambda body, signature, secret: False,
    )

    with pytest.raises(HTTPException) as exc:
        run_webhook(captured_payload())

    assert exc.value.status_code == 400
    assert webhook_mocks.transactions.document["payment_status"] == "initiated"
    webhook_mocks.finalize.assert_not_called()