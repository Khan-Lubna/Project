import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

# Make backend modules importable on Windows
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import server


class FakeShopifyClient:
    def __init__(self, pricing=None, error=None):
        self.pricing = pricing
        self.error = error

    async def get_variant_prices(self, slugs):
        if self.error:
            raise self.error
        return self.pricing


def run_pricing(products):
    return asyncio.run(server._get_shopify_priced_products(products))


@pytest.fixture
def sample_product():
    return {
        "slug": "oura",
        "name": "OURA",
        "price": 100.00,
        "currency": "USD",
        "theme": "dark",
    }


def test_shopify_client_unavailable(monkeypatch, sample_product):
    monkeypatch.setattr(
        server.shopify_client, "shopify_client", None
    )

    with pytest.raises(HTTPException) as exc:
        run_pricing([sample_product])

    assert exc.value.status_code == 503


def test_valid_inr_price(monkeypatch, sample_product):
    fake = FakeShopifyClient({
        "currency": "INR",
        "prices": {"oura": "1149.00"},
    })

    monkeypatch.setattr(
        server.shopify_client, "shopify_client", fake
    )

    result = run_pricing([sample_product])

    assert result[0]["price"] == 1149.00
    assert result[0]["currency"] == "INR"
    assert result[0]["name"] == "OURA"
    assert result[0]["theme"] == "dark"


def test_rejects_non_inr_currency(monkeypatch, sample_product):
    fake = FakeShopifyClient({
        "currency": "USD",
        "prices": {"oura": "100.00"},
    })

    monkeypatch.setattr(
        server.shopify_client, "shopify_client", fake
    )

    with pytest.raises(HTTPException) as exc:
        run_pricing([sample_product])

    assert exc.value.status_code == 503


@pytest.mark.parametrize("price", ["0", "-10", "invalid", "NaN", "Infinity"])
def test_rejects_invalid_prices(monkeypatch, sample_product, price):
    fake = FakeShopifyClient({
        "currency": "INR",
        "prices": {"oura": price},
    })

    monkeypatch.setattr(
        server.shopify_client, "shopify_client", fake
    )

    with pytest.raises(HTTPException) as exc:
        run_pricing([sample_product])

    assert exc.value.status_code == 503


def test_shopify_api_failure(monkeypatch, sample_product):
    fake = FakeShopifyClient(
        error=RuntimeError("Simulated Shopify failure")
    )

    monkeypatch.setattr(
        server.shopify_client, "shopify_client", fake
    )

    with pytest.raises(HTTPException) as exc:
        run_pricing([sample_product])

    assert exc.value.status_code == 503