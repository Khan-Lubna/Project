
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import server


class FakeShopifyClient:
    def __init__(self, prices=None, currency="INR", error=None):
        self.prices = prices or {
            "oura": "1149.00",
            "veloura": "1149.00",
        }
        self.currency = currency
        self.error = error
        self.calls = []

    async def get_variant_prices(self, slugs):
        self.calls.append(slugs)
        if self.error:
            raise self.error
        return {
            "currency": self.currency,
            "prices": self.prices,
        }


class FakePaymentTransactions:
    def __init__(self):
        self.documents = []

    async def insert_one(self, document):
        self.documents.append(document.copy())
        return SimpleNamespace(inserted_id="mock-id")


@pytest.fixture
def checkout_mocks(monkeypatch):
    shopify = FakeShopifyClient()
    transactions = FakePaymentTransactions()

    razorpay_order_create = MagicMock(
        return_value={"id": "order_mock_123"}
    )
    razorpay_client = SimpleNamespace(
        order=SimpleNamespace(create=razorpay_order_create)
    )

    monkeypatch.setattr(
        server.shopify_client, "shopify_client", shopify
    )
    monkeypatch.setattr(server, "rzp_client", razorpay_client)
    monkeypatch.setattr(
        server,
        "db",
        SimpleNamespace(payment_transactions=transactions),
    )
    monkeypatch.setattr(
        server, "RAZORPAY_KEY_ID", "rzp_test_mock"
    )

    return SimpleNamespace(
        shopify=shopify,
        transactions=transactions,
        razorpay_order_create=razorpay_order_create,
    )


def make_request(items):
    return server.OrderCreateRequest(
        customer_name="Test Buyer",
        customer_email="test@example.com",
        shipping_address="Test Address",
        items=items,
    )


def run_checkout(request):
    return asyncio.run(server.create_order(request))


def test_single_product_inr_to_paise(checkout_mocks):
    response = run_checkout(
        make_request([{"slug": "oura", "quantity": 1}])
    )

    assert response.currency == "INR"
    assert response.total == 1149.00
    assert response.amount == 114900
    assert response.rzp_order_id == "order_mock_123"

    payload = checkout_mocks.razorpay_order_create.call_args.args[0]
    assert payload["amount"] == 114900
    assert payload["currency"] == "INR"


def test_multiple_products_and_quantities(checkout_mocks):
    response = run_checkout(
        make_request([
            {"slug": "oura", "quantity": 2},
            {"slug": "veloura", "quantity": 1},
        ])
    )

    assert response.total == 3447.00
    assert response.amount == 344700
    assert checkout_mocks.shopify.calls == [
        ["oura", "veloura"]
    ]


def test_uses_shopify_price_not_static_catalog(checkout_mocks):
    checkout_mocks.shopify.prices["oura"] = "1299.50"

    response = run_checkout(
        make_request([{"slug": "oura", "quantity": 1}])
    )

    assert response.total == 1299.50
    assert response.amount == 129950


def test_unknown_product_returns_400(checkout_mocks):
    with pytest.raises(HTTPException) as exc:
        run_checkout(
            make_request([
                {"slug": "unknown-product", "quantity": 1}
            ])
        )

    assert exc.value.status_code == 400
    assert checkout_mocks.shopify.calls == []
    checkout_mocks.razorpay_order_create.assert_not_called()


def test_empty_cart_returns_400(checkout_mocks):
    with pytest.raises(HTTPException) as exc:
        run_checkout(make_request([]))

    assert exc.value.status_code == 400
    checkout_mocks.razorpay_order_create.assert_not_called()


def test_shopify_unavailable_returns_503(checkout_mocks, monkeypatch):
    monkeypatch.setattr(
        server.shopify_client, "shopify_client", None
    )

    with pytest.raises(HTTPException) as exc:
        run_checkout(
            make_request([{"slug": "oura", "quantity": 1}])
        )

    assert exc.value.status_code == 503
    checkout_mocks.razorpay_order_create.assert_not_called()


def test_shopify_api_failure_returns_503(checkout_mocks):
    checkout_mocks.shopify.error = RuntimeError(
        "Simulated Shopify failure"
    )

    with pytest.raises(HTTPException) as exc:
        run_checkout(
            make_request([{"slug": "oura", "quantity": 1}])
        )

    assert exc.value.status_code == 503
    checkout_mocks.razorpay_order_create.assert_not_called()


def test_wrong_currency_returns_503(checkout_mocks):
    checkout_mocks.shopify.currency = "USD"

    with pytest.raises(HTTPException) as exc:
        run_checkout(
            make_request([{"slug": "oura", "quantity": 1}])
        )

    assert exc.value.status_code == 503
    checkout_mocks.razorpay_order_create.assert_not_called()


def test_razorpay_failure_returns_502(checkout_mocks):
    checkout_mocks.razorpay_order_create.side_effect = RuntimeError(
        "Simulated Razorpay failure"
    )

    with pytest.raises(HTTPException) as exc:
        run_checkout(
            make_request([{"slug": "oura", "quantity": 1}])
        )

    assert exc.value.status_code == 502
    assert checkout_mocks.transactions.documents == []


def test_transaction_saved_correctly(checkout_mocks):
    response = run_checkout(
        make_request([
            {"slug": "oura", "quantity": 2},
            {"slug": "veloura", "quantity": 1},
        ])
    )

    assert len(checkout_mocks.transactions.documents) == 1

    txn = checkout_mocks.transactions.documents[0]

    assert txn["order_id"] == response.order_id
    assert txn["rzp_order_id"] == "order_mock_123"
    assert txn["amount"] == 3447.00
    assert txn["amount_minor"] == 344700
    assert txn["currency"] == "INR"
    assert txn["payment_status"] == "initiated"
    assert len(txn["items"]) == 2
    assert txn["items"][0]["line_total"] == 2298.00
    assert txn["items"][1]["line_total"] == 1149.00


def test_decimal_precision(checkout_mocks):
    checkout_mocks.shopify.prices["oura"] = "999.99"

    response = run_checkout(
        make_request([{"slug": "oura", "quantity": 3}])
    )

    assert response.total == 2999.97
    assert response.amount == 299997