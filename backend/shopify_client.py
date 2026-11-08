import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional

import httpx
from decimal import Decimal

logger = logging.getLogger(__name__)

ORDER_CREATE_MUTATION = """
mutation orderCreate($order: OrderCreateOrderInput!, $options: OrderCreateOptionsInput) {
  orderCreate(order: $order, options: $options) {
    order { id name displayFinancialStatus }
    userErrors { field message }
  }
}
"""

SHOP_QUERY = """
query {
  shop { name }
}
"""


class ShopifyClient:
    def __init__(self, store_url: str, client_id: str, client_secret: str,
                 api_version: str = "2026-04"):
        self.store_url = store_url.strip().replace("https://", "").replace("http://", "").rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_version = api_version
        self.base_url = f"https://{self.store_url}/admin/api/{self.api_version}/graphql.json"
        self.token_url = f"https://{self.store_url}/admin/oauth/access_token"
        self.access_token: Optional[str] = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()
        self._enabled = True
        self._variant_map = self._load_variant_map()

    def _load_variant_map(self) -> Dict[str, str]:
        raw = os.environ.get("SHOPIFY_VARIANT_MAP", "").strip()
        if not raw:
            return {}
        try:
            import json
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                return {}
            return {str(k): str(v) for k, v in parsed.items()}
        except Exception:
            logger.warning("Failed to parse SHOPIFY_VARIANT_MAP; Shopify orders may fail.")
            return {}

    def _get_variant_gid(self, slug: str) -> Optional[str]:
        return self._variant_map.get(slug)

    async def get_variant_prices(self, slugs: list[str]) -> Dict[str, Any]:
        """Fetch current variant prices and store currency from Shopify."""

        variant_ids = {}
        for slug in slugs:
            variant_gid = self._get_variant_gid(slug)
            if not variant_gid:
                raise ValueError(
                    f"No Shopify variant mapping configured for: {slug}"
                )
            variant_ids[slug] = variant_gid

        if not variant_ids:
            raise ValueError("No products supplied for price lookup")

        query = """
        query VariantPrices($ids: [ID!]!) {
          shop {
            currencyCode
          }
          nodes(ids: $ids) {
            ... on ProductVariant {
              id
              price
            }
          }
        }
        """

        result = await self._graphql(
            query,
            {"ids": list(variant_ids.values())},
        )

        if result.get("errors"):
            raise RuntimeError(
                f"Shopify price lookup failed: {result['errors']}"
            )

        data = result.get("data") or {}
        currency = (data.get("shop") or {}).get("currencyCode")
        nodes = data.get("nodes") or []

        if not currency:
            raise RuntimeError("Shopify did not return the store currency")

        prices_by_id = {
            node["id"]: node["price"]
            for node in nodes
            if isinstance(node, dict) and node.get("id") and node.get("price") is not None
        }

        prices = {}
        for slug, variant_gid in variant_ids.items():
            price = prices_by_id.get(variant_gid)
            if price is None:
                raise RuntimeError(
                    f"Shopify did not return a price for product: {slug}"
                )
            prices[slug] = price

        return {
            "currency": currency,
            "prices": prices,
        }

    async def _get_access_token(self) -> str:
        if self.access_token and time.monotonic() < self._token_expires_at - 300:
            return self.access_token

        async with self._token_lock:
            if self.access_token and time.monotonic() < self._token_expires_at - 300:
                return self.access_token
            if not self.client_id or not self.client_secret:
                raise RuntimeError("Shopify Client ID or Client Secret is not configured")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                   self.token_url,
                   data={
                       "grant_type": "client_credentials",
                       "client_id": self.client_id,
                       "client_secret": self.client_secret,
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                   },
         )
                response.raise_for_status()
                token_data = response.json()

            token = token_data.get("access_token")
            expires_in = int(token_data.get("expires_in", 0))
            if not token or expires_in <= 0:
                raise RuntimeError("Shopify token response did not contain a valid access token")

            self.access_token = token
            self._token_expires_at = time.monotonic() + expires_in
            logger.info("Shopify Admin API access token obtained; expires in %s seconds", expires_in)
            return token

    async def _graphql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        token = await self._get_access_token()
        headers = {
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.base_url,
                json={"query": query, "variables": variables or {}},
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def validate_token(self) -> Dict[str, Any]:
        if not self.store_url or not self.client_id or not self.client_secret:
            return {"valid": False, "error": "Shopify credentials not configured"}
        try:
            shop_result = await self._graphql(SHOP_QUERY)
            if shop_result.get("errors"):
                return {"valid": False, "error": f"Shopify GraphQL error: {shop_result['errors']}"}
            shop_name = shop_result.get("data", {}).get("shop", {}).get("name")
            if not shop_name:
                return {"valid": False, "error": "Shopify returned no shop information"}
            return {"valid": True, "error": None, "shop": shop_name}
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300] if exc.response is not None else ""
            status = exc.response.status_code if exc.response is not None else "unknown"
            return {"valid": False, "error": f"HTTP {status}: {body}"}
        except Exception as exc:
            return {"valid": False, "error": str(exc)}

    def _build_order_input(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        full_name = order_data.get("customer_name", "") or ""
        name_parts = full_name.strip().split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        line_items = []
        missing_variants = []
        for item in order_data.get("items", []):
            slug = item.get("slug", "")
            variant_gid = self._get_variant_gid(slug)

            if not variant_gid:
                missing_variants.append(slug)
                continue

            quantity = item.get("quantity", 1)

            if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
                raise ValueError(
                    f"Invalid quantity for product '{slug}': {quantity}"
                )

            line_items.append({
                 "variantId": variant_gid,
                 "quantity": quantity,
            })

        if missing_variants:
            raise ValueError(
                "No Shopify variant mapping configured for slugs: "
                f"{', '.join(missing_variants)}. "
                "Set SHOPIFY_VARIANT_MAP as JSON mapping local slugs to Shopify variant GIDs."
            )

        address_struct = order_data.get("address_struct") or {}
        shipping_address_str = order_data.get("shipping_address", "") or ""

        required_address_fields = {
            "line1": "Address Line 1",
            "city": "City",
            "state": "State",
            "postal_code": "Postal Code",
            "country": "Country",
        }

        missing_fields = [
            label
            for field, label in required_address_fields.items()
            if not str(address_struct.get(field) or "").strip()
        ]

        if missing_fields:
            raise ValueError(
                "Missing required shipping address fields: "
                + ", ".join(missing_fields)
            )

        def _country_code(name: str) -> str:
            mapping = {
                "india": "IN",
                "in": "IN",
            }

            country = (name or "India").strip().lower()

            if country not in mapping:
                raise ValueError(f"Unsupported country: {name}")

            return mapping[country]

        def _province_code(state: str) -> str:
            mapping = {
                "maharashtra": "MH",
                "delhi": "DL",
                "karnataka": "KA",
                "gujarat": "GJ",
                "goa": "GA",
                "rajasthan": "RJ",
                "uttar pradesh": "UP",
                "madhya pradesh": "MP",
                "west bengal": "WB",
                "tamil nadu": "TN",
                "telangana": "TS",
                "kerala": "KL",
                "bihar": "BR",
                "punjab": "PB",
                "haryana": "HR",
                "odisha": "OD",
                "assam": "AS",
            }

            value = (state or "").strip()

            if not value:
                return ""

            if len(value) == 2:
                return value.upper()

            code = mapping.get(value.lower())

            if not code:
                raise ValueError(
                    f"Unsupported Indian state: {state}. "
                    "Please add its Shopify province code."
                )

            return code

        country_code = _country_code(
            address_struct.get("country") or "India"
        )

        shipping_address = {
            "address1": address_struct.get("line1") or (
                shipping_address_str.split("\n")[0]
                if shipping_address_str else ""
            ),
            "address2": address_struct.get("line2") or "",
            "city": address_struct.get("city") or "",
            "provinceCode": _province_code(
                address_struct.get("state") or ""
            ),
            "countryCode": country_code,
            "zip": address_struct.get("postal_code") or "",
            "phone": order_data.get("customer_contact") or "",
        }

        billing_address = dict(shipping_address)
        custom_attributes = [
            {"key": "MOSSERO Order ID", "value": order_data.get("order_id", "")},
            {"key": "Razorpay Order", "value": order_data.get("rzp_order_id", "")},
            {"key": "Razorpay Payment", "value": order_data.get("rzp_payment_id", "")},
        ]

        return {
            "lineItems": line_items,
            "customer": {
              "toUpsert": {
              "firstName": first_name,
              "lastName": last_name,
              "email": order_data.get("customer_email", ""),
              "phone": order_data.get("customer_contact") or "",
            }
        },
            "shippingAddress": shipping_address,
            "billingAddress": billing_address,
            "financialStatus": "PAID",
            "customAttributes": custom_attributes,
            "tags": "mossero,razorpay-paid",
            "sourceName": "MOSERO API",
        }


    async def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._enabled:
            return {
                "success": False,
                "outcome": "failed",
                "error": "Shopify integration disabled",
            }

        if not self.store_url or not self.client_id or not self.client_secret:
            logger.warning("Shopify not configured - skipping order creation")
            return {
                "success": False,
                "outcome": "failed",
                "error": "Shopify not configured",
            }

                # Verify paid prices against current Shopify prices before order creation.
        try:
            items = order_data.get("items", [])
            slugs = list(dict.fromkeys(item["slug"] for item in items))

            pricing = await self.get_variant_prices(slugs)
            current_currency = pricing["currency"]
            current_prices = pricing["prices"]
            paid_currency = (order_data.get("currency") or "").upper()

            if current_currency != paid_currency or current_currency != "INR":
                raise ValueError(
                    f"Currency mismatch: paid={paid_currency}, "
                    f"Shopify={current_currency}"
                )

            expected_total = Decimal("0")
            for item in items:
                slug = item["slug"]
                quantity = item.get("quantity")

                if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
                    raise ValueError(f"Invalid quantity for {slug}")

                paid_price = Decimal(str(item["unit_price"])).quantize(
                    Decimal("0.01")
                )
                current_price = Decimal(str(current_prices[slug])).quantize(
                    Decimal("0.01")
                )

                if not paid_price.is_finite() or paid_price <= 0:
                    raise ValueError(f"Invalid paid price for {slug}")

                if paid_price != current_price:
                    raise ValueError(
                        f"Price mismatch for {slug}: customer paid "
                        f"{paid_price}, current Shopify price is {current_price}"
                    )

                expected_total += paid_price * quantity

            recorded_total = Decimal(str(order_data["total"])).quantize(
                Decimal("0.01")
            )
            expected_total = expected_total.quantize(Decimal("0.01"))

            if recorded_total != expected_total:
                raise ValueError(
                    f"Order total mismatch: recorded={recorded_total}, "
                    f"calculated={expected_total}"
                )

            # Build the Shopify input only after price validation succeeds.
            shopify_input = self._build_order_input(order_data)

        except Exception as exc:
            logger.error(
                "Shopify order price/input validation failed for %s: %s",
                order_data.get("order_id"),
                exc,
            )
            return {
                "success": False,
                "outcome": "failed",
                "error": str(exc),
            }

        # Submit the order to Shopify.
        try:
            result = await self._graphql(
                ORDER_CREATE_MUTATION,
                {
                    "order": shopify_input,
                    "options": {
                        "sendReceipt": False,
                        "sendFulfillmentReceipt": False,
                    },
                },
            )

            gql_errors = result.get("errors", [])
            if gql_errors:
                error_messages = "; ".join(
                    err.get("message", str(err)) for err in gql_errors
                )
                logger.error("Shopify GraphQL errors: %s", error_messages)
                lower_msg = error_messages.lower()

                if any(
                    keyword in lower_msg
                    for keyword in (
                        "access token",
                        "permission",
                        "scope",
                        "auth",
                        "unauthorized",
                    )
                ):
                    return {
                        "success": False,
                        "outcome": "failed",
                        "error": (
                            "Shopify permission error: the access token is missing "
                            "required scopes. Check that the app has the required "
                            "Admin API scopes. "
                            f"Detail: {error_messages}"
                        ),
                        "gql_errors": gql_errors,
                    }

                return {
                    "success": False,
                    "outcome": "unknown",
                    "error": f"Shopify API error: {error_messages}",
                    "gql_errors": gql_errors,
                }

            order_create = result.get("data", {}).get("orderCreate", {})
            user_errors = order_create.get("userErrors", [])

            if user_errors:
                error_messages = "; ".join(
                    f"{error.get('field', '')}: {error.get('message', '')}"
                    for error in user_errors
                )
                logger.error("Shopify orderCreate userErrors: %s", error_messages)
                return {
                    "success": False,
                    "outcome": "failed",
                    "error": f"Shopify validation error: {error_messages}",
                    "user_errors": user_errors,
                }

            order_data_resp = order_create.get("order")
            if not order_data_resp:
                return {
                    "success": False,
                    "outcome": "unknown",
                    "error": "Shopify returned no order data",
                }

            shopify_order_id = order_data_resp.get("id", "")
            order_number = order_data_resp.get("name")

            if not shopify_order_id:
                return {
                    "success": False,
                    "outcome": "unknown",
                    "error": "Shopify returned an order without an ID",
                }

            logger.info(
                "Shopify order created successfully: %s (%s)",
                shopify_order_id,
                order_number,
            )

            return {
                "success": True,
                "outcome": "success",
                "shopify_order_id": shopify_order_id,
                "order_number": order_number,
                "shopify_data": order_data_resp,
            }

        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300] if exc.response is not None else ""
            status = (
                exc.response.status_code
                if exc.response is not None
                else "unknown"
            )
            logger.error("Shopify HTTP error: %s - %s", status, body)

            return {
                "success": False,
                "outcome": "unknown",
                "error": f"Shopify HTTP error: {status}",
                "status_code": status,
            }

        except Exception as exc:
            logger.error("Exception creating Shopify order: %s", str(exc))
            return {
                "success": False,
                "outcome": "unknown",
                "error": str(exc),
            }

    def disable(self):
        self._enabled = False
        logger.warning("Shopify integration disabled due to errors")


shopify_client = None


def init_shopify_client(store_url: str, client_id: str, client_secret: str,
                        api_version: str = "2026-04"):
    global shopify_client
    if store_url and client_id and client_secret:
        shopify_client = ShopifyClient(store_url, client_id, client_secret, api_version)
        logger.info("Shopify client initialized")
    else:
        shopify_client = None
        logger.warning("Shopify Client ID/Secret not provided - Shopify integration disabled")


async def create_shopify_order(order_data: Dict[str, Any]) -> Dict[str, Any]:
    if shopify_client is None:
        logger.warning("Shopify client not initialized")
        return {
            "success": False,
            "outcome": "failed",
            "error": "Shopify client not initialized",
        }
    return await shopify_client.create_order(order_data)
