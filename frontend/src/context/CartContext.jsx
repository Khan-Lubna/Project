import { createContext, useContext, useEffect, useState, useMemo } from "react";

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

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  }, [items]);

  const addItem = (product, qty = 1) => {
    setItems((prev) => {
      const existing = prev.find((i) => i.slug === product.slug);
      if (existing) {
        return prev.map((i) =>
          i.slug === product.slug ? { ...i, quantity: i.quantity + qty } : i
        );
      }
      return [
        ...prev,
        {
          slug: product.slug,
          name: product.name,
          price: product.price,
          image: product.image,
          size: product.size,
          quantity: qty,
        },
      ];
    });
  };

  const removeItem = (slug) =>
    setItems((prev) => prev.filter((i) => i.slug !== slug));

  const updateQty = (slug, quantity) =>
    setItems((prev) =>
      prev.map((i) => (i.slug === slug ? { ...i, quantity } : i))
    );

  const clear = () => setItems([]);

  const totals = useMemo(() => {
    const subtotal = items.reduce((s, i) => s + i.price * i.quantity, 0);
    const count = items.reduce((s, i) => s + i.quantity, 0);
    return { subtotal, count };
  }, [items]);

  return (
    <CartContext.Provider
      value={{ items, addItem, removeItem, updateQty, clear, ...totals }}
    >
      {children}
    </CartContext.Provider>
  );
}

export const useCart = () => useContext(CartContext);
