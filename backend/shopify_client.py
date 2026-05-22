import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ShopifyClient:
    def __init__(self, store_url: str, access_token: str, api_version: str = "2024-01"):
        self.store_url = store_url.rstrip('/')
        self.access_token = access_token
        self.api_version = api_version
        self.base_url = f"https://{self.store_url}/admin/api/{self.api_version}"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def create_order(self, order_data: Dict[Any, Any]) -> Dict[Any, Any]:
        """
        Create an order in Shopify
        """
        if not self.store_url or not self.access_token:
            logger.warning("Shopify not configured - skipping order creation")
            return {"success": False, "error": "Shopify not configured"}

        try:
            # Transform our order data to Shopify format
            line_items = []
            for item in order_data.get("items", []):
                line_items.append({
                    "title": item.get("name", "Unknown Product"),
                    "quantity": item.get("quantity", 1),
                    "price": str(item.get("unit_price", 0.0)),
                    # Note: For a real implementation, you'd need to match products by SKU or title
                    # This is a simplified version that creates custom line items
                })

            shopify_order = {
                "order": {
                    "line_items": line_items,
                    "customer": {
                        "first_name": order_data.get("customer_name", "").split(" ")[0] if order_data.get("customer_name") else "",
                        "last_name": " ".join(order_data.get("customer_name", "").split(" ")[1:]) if len(order_data.get("customer_name", "").split(" ")) > 1 else "",
                        "email": order_data.get("customer_email", ""),
                    },
                    "billing_address": {
                        "first_name": order_data.get("customer_name", "").split(" ")[0] if order_data.get("customer_name") else "",
                        "last_name": " ".join(order_data.get("customer_name", "").split(" ")[1:]) if len(order_data.get("customer_name", "").split(" ")) > 1 else "",
                    },
                    "shipping_address": {
                        "address1": order_data.get("shipping_address", "").split("\n")[0] if order_data.get("shipping_address") else "",
                        "address2": "\n".join(order_data.get("shipping_address", "").split("\n")[1:]) if len(order_data.get("shipping_address", "").split("\n")) > 1 else "",
                        "city": "",  # Would need to parse from address
                        "province": "",  # Would need to parse from address
                        "country": "India",
                        "zip": "",  # Would need to parse from address
                    },
                    "financial_status": "paid",
                    "fulfillment_status": "unfulfilled",
                    "total_price": str(order_data.get("total", 0.0)),
                    "currency": order_data.get("currency", "USD"),
                    "note": f"Order ID: {order_data.get('order_id', '')} | Razorpay Order: {order_data.get('rzp_order_id', '')}",
                    "tags": "mossero,razorpay-paid"
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/orders.json",
                    json=shopify_order,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code in (200, 201):
                    result = response.json()
                    logger.info(f"Shopify order created successfully: {result['order']['id']}")
                    return {
                        "success": True,
                        "shopify_order_id": result["order"]["id"],
                        "order_number": result["order"]["order_number"],
                        "shopify_data": result["order"]
                    }
                else:
                    logger.error(f"Failed to create Shopify order: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": f"Shopify API error: {response.status_code} - {response.text}",
                        "status_code": response.status_code
                    }

        except Exception as e:
            logger.error(f"Exception creating Shopify order: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

# Global shopify client instance (will be initialized in server.py)
shopify_client = None

def init_shopify_client(store_url: str, access_token: str, api_version: str = "2024-01"):
    global shopify_client
    if store_url and access_token:
        shopify_client = ShopifyClient(store_url, access_token, api_version)
        logger.info("Shopify client initialized")
    else:
        shopify_client = None
        logger.warning("Shopify credentials not provided - Shopify integration disabled")

async def create_shopify_order(order_data: Dict[Any, Any]) -> Dict[Any, Any]:
    """
    Convenience function to create a Shopify order
    """
    global shopify_client
    if shopify_client is None:
        logger.warning("Shopify client not initialized")
        return {"success": False, "error": "Shopify client not initialized"}
    
    return await shopify_client.create_order(order_data)