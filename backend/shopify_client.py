import httpx
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

ORDER_CREATE_MUTATION = """
mutation orderCreate($order: OrderCreateOrderInput!, $options: OrderCreateOptionsInput) {
  orderCreate(order: $order, options: $options) {
    order {
      id
      name
      displayFinancialStatus
    }
    userErrors {
      field
      message
    }
  }
}
"""

SHOP_QUERY = """
query {
  shop {
    name
  }
}
"""


class ShopifyClient:
    def __init__(self, store_url: str, access_token: str, api_version: str = "2024-01"):
        self.store_url = store_url.rstrip('/')
        self.access_token = access_token
        self.api_version = api_version
        self.base_url = f"https://{self.store_url}/admin/api/{self.api_version}/graphql.json"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }
        self._enabled = True
        self._variant_map = self._load_variant_map()

    def _load_variant_map(self) -> Dict[str, str]:
        raw = os.environ.get("SHOPIFY_VARIANT_MAP", "").strip()
        if not raw:
            return {}
        try:
            parsed = __import__("json").loads(raw)
            if not isinstance(parsed, dict):
                return {}
            return {str(k): str(v) for k, v in parsed.items()}
        except Exception:
            logger.warning("Failed to parse SHOPIFY_VARIANT_MAP; Shopify orders may fail.")
            return {}

    def _get_variant_gid(self, slug: str) -> Optional[str]:
        return self._variant_map.get(slug)

    async def _graphql(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                json={"query": query, "variables": variables or {}},
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def validate_token(self) -> Dict[str, Any]:
        if not self.store_url or not self.access_token:
            return {"valid": False, "error": "Shopify credentials not configured"}

        try:
            shop_result = await self._graphql(SHOP_QUERY)
            if "errors" in shop_result:
                return {
                    "valid": False,
                    "error": f"Shopify token invalid: {shop_result['errors']}",
                }

            return {
                "valid": True,
                "error": None,
            }
        except httpx.HTTPStatusError as e:
            body = e.response.text[:300] if e.response is not None else ""
            return {
                "valid": False,
                "error": f"HTTP {e.response.status_code}: {body}",
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }

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
            if variant_gid:
                line_items.append({
                    "variantId": variant_gid,
                    "quantity": item.get("quantity", 1),
                })
            else:
                missing_variants.append(slug)

        if missing_variants:
            raise ValueError(
                "No Shopify variant mapping configured for slugs: "
                f"{', '.join(missing_variants)}. "
                "Set SHOPIFY_VARIANT_MAP as JSON mapping local slugs to Shopify variant GIDs."
            )

        address_struct = order_data.get("address_struct") or {}
        shipping_address_str = order_data.get("shipping_address", "") or ""

        def _country_code(name: str) -> str:
            if not name:
                return "IN"
            mapping = {
                "india": "IN",
                "united states": "US",
                "usa": "US",
                "united kingdom": "GB",
                "uk": "GB",
                "canada": "CA",
                "australia": "AU",
            }
            return mapping.get(name.strip().lower(), name)

        shipping_address = {
            "address1": address_struct.get("line1") or (shipping_address_str.split("\n")[0] if shipping_address_str else ""),
            "address2": address_struct.get("line2") or "",
            "city": address_struct.get("city") or "",
            "province": address_struct.get("state") or "",
            "country": _country_code(address_struct.get("country") or "India"),
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
                "firstName": first_name,
                "lastName": last_name,
                "email": order_data.get("customer_email", ""),
                "phone": order_data.get("customer_contact") or "",
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
            return {"success": False, "error": "Shopify integration disabled"}

        if not self.store_url or not self.access_token:
            logger.warning("Shopify not configured - skipping order creation")
            return {"success": False, "error": "Shopify not configured"}

        try:
            shopify_input = self._build_order_input(order_data)
            result = await self._graphql(
                ORDER_CREATE_MUTATION,
                {
                    "order": shopify_input,
                    "options": {
                        "sendOrderConfirmationEmail": False,
                        "sendFulfillmentReceiptEmail": False,
                    },
                },
            )

            gql_errors = result.get("errors", [])
            if gql_errors:
                error_messages = "; ".join(err.get("message", str(err)) for err in gql_errors)
                logger.error(f"Shopify GraphQL errors: {error_messages}")
                lower_msg = error_messages.lower()
                if any(k in lower_msg for k in ("access token", "permission", "scope", "auth", "unauthorized")):
                    return {
                        "success": False,
                        "error": (
                            "Shopify permission error: the access token is missing required scopes. "
                            "Add 'write_orders' (and 'read_products' if variant lookup is needed) "
                            f"to your Shopify custom app. Detail: {error_messages}"
                        ),
                        "gql_errors": gql_errors,
                    }
                return {
                    "success": False,
                    "error": f"Shopify API error: {error_messages}",
                    "gql_errors": gql_errors,
                }

            order_create = result.get("data", {}).get("orderCreate", {})
            user_errors = order_create.get("userErrors", [])
            if user_errors:
                error_messages = "; ".join(f"{e.get('field', '')}: {e.get('message', '')}" for e in user_errors)
                logger.error(f"Shopify orderCreate userErrors: {error_messages}")
                return {
                    "success": False,
                    "error": f"Shopify validation error: {error_messages}",
                    "user_errors": user_errors,
                }

            order_data_resp = order_create.get("order")
            if not order_data_resp:
                return {
                    "success": False,
                    "error": "Shopify returned no order data",
                }

            shopify_order_id = order_data_resp.get("id", "")
            order_number = order_data_resp.get("name")
            logger.info(f"Shopify order created successfully: {shopify_order_id} ({order_number})")
            return {
                "success": True,
                "shopify_order_id": shopify_order_id,
                "order_number": order_number,
                "shopify_data": order_data_resp,
            }

        except httpx.HTTPStatusError as e:
            body = e.response.text[:300] if e.response is not None else ""
            logger.error(f"Shopify HTTP error: {e.response.status_code} - {body}")
            return {
                "success": False,
                "error": f"Shopify HTTP error: {e.response.status_code}",
                "status_code": e.response.status_code,
            }
        except Exception as e:
            logger.error(f"Exception creating Shopify order: {str(e)}")
            return {
                "success": False,
                "error": str(e),
            }

    def disable(self):
        self._enabled = False
        logger.warning("Shopify integration disabled due to errors")


shopify_client = None


def init_shopify_client(store_url: str, access_token: str, api_version: str = "2024-01"):
    global shopify_client
    if store_url and access_token:
        shopify_client = ShopifyClient(store_url, access_token, api_version)
        logger.info("Shopify client initialized")
    else:
        shopify_client = None
        logger.warning("Shopify credentials not provided - Shopify integration disabled")


async def create_shopify_order(order_data: Dict[str, Any]) -> Dict[str, Any]:
    if shopify_client is None:
        logger.warning("Shopify client not initialized")
        return {"success": False, "error": "Shopify client not initialized"}

    return await shopify_client.create_order(order_data)
