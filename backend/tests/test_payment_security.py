import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import server

class FakePaymentTransactions:
    def __init__(self, document):
        self.document = document.copy()
        self.update_calls = []

    async def find_one(self, query, projection=None):
        if query.get("order_id") != self.document.get("order_id"):
            return None
        return self.document.copy()

    async def update_one(self, query, update):
        self.update_calls.append((query, update))

        if query.get("order_id") != self.document.get("order_id"):
            return

        status_filter = query.get("payment_status")
        if isinstance(status_filter, dict):
            if status_filter.get("$ne") == "paid":
                if self.document.get("payment_status") == "paid":
                    return

        self.document.update(update.get("$set", {}))


@pytest.fixture
def payment_mocks(monkeypatch):
    txn = {
        "order_id": "test-order-123",
        "rzp_order_id": "rzp-order-123",
        "rzp_payment_id": None,
        "amount_minor": 114900,
        "currency": "INR",
        "payment_status": "initiated",
        "status": "pending",
    }

    transactions = FakePaymentTransactions(txn)
    finalize = AsyncMock()

    payment_fetch = MagicMock(
    return_value={
        "id": "pay-123",
        "order_id": "rzp-order-123",
        "status": "captured",
        "amount": 114900,
        "currency": "INR",
    }
)

    monkeypatch.setattr(
        server,
        "db",
        SimpleNamespace(payment_transactions=transactions),
    )
    monkeypatch.setattr(
    server,
    "rzp_client",
    SimpleNamespace(
        payment=SimpleNamespace(fetch=payment_fetch)
      ),
    )
    monkeypatch.setattr(
        server,
        "_verify_signature",
        lambda payload, signature, secret: True,
    )
    monkeypatch.setattr(
        server,
        "_finalize_paid_order",
        finalize,
    )

    return SimpleNamespace(
        transactions=transactions,
        finalize=finalize,
        payment_fetch=payment_fetch,
    )


def make_verify_request():
    return server.VerifyPaymentRequest(
        order_id="test-order-123",
        razorpay_order_id="rzp-order-123",
        razorpay_payment_id="pay-123",
        razorpay_signature="valid-mock-signature",
    )


def run_verify(request):
    return asyncio.run(server.verify_payment(request))


def test_invalid_signature_does_not_mark_payment_paid(
    payment_mocks, monkeypatch
):
    monkeypatch.setattr(
        server,
        "_verify_signature",
        lambda payload, signature, secret: False,
    )

    with pytest.raises(HTTPException) as exc:
        run_verify(make_verify_request())

    assert exc.value.status_code == 400
    assert payment_mocks.transactions.document["payment_status"] == "initiated"
    payment_mocks.finalize.assert_not_called()


def test_invalid_signature_does_not_finalize_already_paid_transaction(
    payment_mocks, monkeypatch
):
    payment_mocks.transactions.document["payment_status"] = "paid"
    payment_mocks.transactions.document["status"] = "complete"

    monkeypatch.setattr(
        server,
        "_verify_signature",
        lambda payload, signature, secret: False,
    )

    with pytest.raises(HTTPException) as exc:
        run_verify(make_verify_request())

    assert exc.value.status_code == 400
    payment_mocks.finalize.assert_not_called()
    assert payment_mocks.transactions.document["payment_status"] == "paid"
    assert payment_mocks.transactions.update_calls == []


def test_valid_signature_marks_payment_paid_and_finalizes(
    payment_mocks,
):
    response = run_verify(make_verify_request())

    assert response["payment_status"] == "paid"
    assert payment_mocks.transactions.document["payment_status"] == "paid"
    assert payment_mocks.transactions.document["rzp_payment_id"] == "pay-123"
    payment_mocks.finalize.assert_awaited_once()


def test_rejects_payment_not_captured(payment_mocks):
    payment_mocks.payment_fetch.return_value["status"] = "authorized"

    with pytest.raises(HTTPException) as exc:
        run_verify(make_verify_request())

    assert exc.value.status_code == 400
    assert payment_mocks.transactions.document["payment_status"] == "initiated"
    payment_mocks.finalize.assert_not_called()


def test_rejects_payment_amount_mismatch(payment_mocks):
    payment_mocks.payment_fetch.return_value["amount"] = 100

    with pytest.raises(HTTPException) as exc:
        run_verify(make_verify_request())

    assert exc.value.status_code == 400
    assert payment_mocks.transactions.document["payment_status"] == "initiated"
    payment_mocks.finalize.assert_not_called()


def test_rejects_payment_currency_mismatch(payment_mocks):
    payment_mocks.payment_fetch.return_value["currency"] = "USD"

    with pytest.raises(HTTPException) as exc:
        run_verify(make_verify_request())

    assert exc.value.status_code == 400
    assert payment_mocks.transactions.document["payment_status"] == "initiated"
    payment_mocks.finalize.assert_not_called()


def test_rejects_payment_order_mismatch(payment_mocks):
    payment_mocks.payment_fetch.return_value["order_id"] = "another-order"

    with pytest.raises(HTTPException) as exc:
        run_verify(make_verify_request())

    assert exc.value.status_code == 400
    assert payment_mocks.transactions.document["payment_status"] == "initiated"
    payment_mocks.finalize.assert_not_called()


def test_razorpay_fetch_failure_does_not_mark_paid(payment_mocks):
    payment_mocks.payment_fetch.side_effect = RuntimeError(
        "Simulated Razorpay API failure"
    )

    with pytest.raises(HTTPException) as exc:
        run_verify(make_verify_request())

    assert exc.value.status_code == 502
    assert payment_mocks.transactions.document["payment_status"] == "initiated"
    payment_mocks.finalize.assert_not_called()


def test_already_paid_transaction_rejects_different_payment_id(
    payment_mocks,
):
    payment_mocks.transactions.document["payment_status"] = "paid"
    payment_mocks.transactions.document["status"] = "complete"
    payment_mocks.transactions.document["rzp_payment_id"] = "pay-existing"

    with pytest.raises(HTTPException) as exc:
        run_verify(make_verify_request())

    assert exc.value.status_code == 409
    payment_mocks.finalize.assert_not_called()
    assert payment_mocks.transactions.document["rzp_payment_id"] == "pay-existing"