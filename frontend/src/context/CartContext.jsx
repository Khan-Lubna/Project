import { createContext, useContext, useEffect, useState, useMemo } from "react";
import {
  USE_SHOPIFY_CATALOG,
  fetchProducts,
} from "../lib/shopify";

const CartContext = createContext(null);

const STORAGE_KEY = "mossero_cart_v1";

export function CartProvider({ children }) {
  const [items, setItems] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  });
  const [shopifyPriceMap, setShopifyPriceMap] = useState(null);
  const [shopifyPricesLoading, setShopifyPricesLoading] = useState(
    USE_SHOPIFY_CATALOG
  );

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  }, [items]);

  // const addItem = (product, qty = 1) => {
  //   setItems((prev) => {
  //     const existing = prev.find((i) => i.slug === product.slug);
  //     if (existing) {
  //       return prev.map((i) =>
  //         i.slug === product.slug ? { ...i, quantity: i.quantity + qty } : i
  //       );
  //     }
  //     return [
  //       ...prev,
  //       {
  //         slug: product.slug,
  //         name: product.name,
  //         price: product.price,
  //         image: product.image,
  //         size: product.size,
  //         quantity: qty,
  //       },
  //     ];
  //   });
  // };

  useEffect(() => {
    if (!USE_SHOPIFY_CATALOG) return;

    let active = true;

    fetchProducts()
      .then((products) => {
        if (!active) return;

        const priceMap = new Map(
          products.map((product) => [
            product.slug,
            {
              price: Number(product.price),
              currency: product.currency,
            },
          ])
        );

        setShopifyPriceMap(priceMap);
        setShopifyPricesLoading(false);
      })
      .catch((error) => {
        console.error("Unable to refresh cart prices:", error);

        if (active) {
          setShopifyPricesLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!USE_SHOPIFY_CATALOG || !shopifyPriceMap) return;

    setItems((previousItems) => {
      let changed = false;

      const updatedItems = previousItems.map((item) => {
        const latest = shopifyPriceMap.get(item.slug);

        if (
          !latest ||
          !Number.isFinite(latest.price) ||
          latest.price <= 0 ||
          latest.currency !== "INR"
        ) {
          return item;
        }

        if (
          item.price === latest.price &&
          item.currency === latest.currency
        ) {
          return item;
        }

        changed = true;
        return { ...item, ...latest };
      });

      return changed ? updatedItems : previousItems;
    });
  }, [shopifyPriceMap, items]);

  const addItem = (product, qty = 1) => {
    const availableVariant =
      product.shopify?.variants?.find(
        (variant) => variant.availableForSale
      ) || product.shopify?.variants?.[0] || null;

    const cartItem = {
      slug: product.slug,
      name: product.name,
      price: product.price,
      currency: product.currency || "INR",
      image: product.image,
      size: product.size,
      quantity: qty,

      // Shopify identifiers
      shopifyProductId: product.shopify?.productId || null,
      shopifyVariantId: availableVariant?.id || null,
    };

    setItems((prev) => {
      const existing = prev.find(
        (item) => item.slug === product.slug
      );

      if (existing) {
        return prev.map((item) =>
          item.slug === product.slug
            ? {
              ...item,
              quantity: item.quantity + qty,
              shopifyProductId:
                cartItem.shopifyProductId || item.shopifyProductId,
              shopifyVariantId:
                cartItem.shopifyVariantId || item.shopifyVariantId,
            }
            : item
        );
      }

      return [...prev, cartItem];
    });
  };

  const removeItem = (slug) =>
    setItems((prev) => prev.filter((i) => i.slug !== slug));

  const updateQty = (slug, quantity) =>
    setItems((prev) =>
      prev.map((i) => (i.slug === slug ? { ...i, quantity } : i))
    );

  const clear = () => setItems([]);

  const shopifyPricesStatus = !USE_SHOPIFY_CATALOG
    ? "disabled"
    : shopifyPricesLoading
      ? "loading"
      : shopifyPriceMap &&
        items.every((item) => {
          const latest = shopifyPriceMap.get(item.slug);

          return (
            latest &&
            Number.isFinite(latest.price) &&
            latest.price > 0 &&
            latest.currency === "INR" &&
            item.price === latest.price &&
            item.currency === latest.currency
          );
        })
        ? "verified"
        : "error";

  const totals = useMemo(() => {
    const subtotal = items.reduce((s, i) => s + i.price * i.quantity, 0);
    const count = items.reduce((s, i) => s + i.quantity, 0);
    return { subtotal, count };
  }, [items]);

  return (
    <CartContext.Provider
      value={{
        items,
        addItem,
        removeItem,
        updateQty,
        clear,
        shopifyPricesStatus,
        ...totals,
      }}
    >
      {children}
    </CartContext.Provider>
  );
}

export const useCart = () => useContext(CartContext);
