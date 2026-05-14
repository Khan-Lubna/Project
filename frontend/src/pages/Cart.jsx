import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { Trash2, Minus, Plus } from "lucide-react";
import { toast } from "sonner";
import { useCart } from "../context/CartContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Cart() {
  const navigate = useNavigate();
  const { items, removeItem, updateQty, subtotal, clear } = useCart();
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    customer_name: "",
    customer_email: "",
    customer_contact: "",
    address_line1: "",
    address_line2: "",
    city: "",
    state: "",
    postal_code: "",
    country: "India",
    notes: "",
  });

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const reserve = async (e) => {
    e.preventDefault();
    const required = [
      "customer_name",
      "customer_email",
      "customer_contact",
      "address_line1",
      "city",
      "state",
      "postal_code",
    ];
    if (required.some((k) => !form[k])) {
      toast.error("Please complete all required fields.");
      return;
    }
    setSubmitting(true);
    try {
      const shipping_address = [
        form.address_line1,
        form.address_line2,
        `${form.city}, ${form.state} ${form.postal_code}`,
        form.country,
      ]
        .filter(Boolean)
        .join("\n");

      const res = await axios.post(`${API}/checkout/concierge`, {
        customer_name: form.customer_name,
        customer_email: form.customer_email,
        customer_contact: form.customer_contact,
        shipping_address,
        address_struct: {
          line1: form.address_line1,
          line2: form.address_line2 || "",
          city: form.city,
          state: form.state,
          postal_code: form.postal_code,
          country: form.country || "India",
        },
        notes: form.notes,
        items: items.map((i) => ({ slug: i.slug, quantity: i.quantity })),
      });

      clear();
      navigate(
        `/cart/success?order_id=${encodeURIComponent(res.data.order_id)}&mode=concierge`
      );
    } catch (err) {
      toast.error("Reservation failed", {
        description:
          err?.response?.data?.detail ||
          err.message ||
          "Please try again or write to mossero.in@gmail.com.",
      });
      setSubmitting(false);
    }
  };

  return (
    <div data-testid="cart-page" className="bg-cream pt-32 lg:pt-44 pb-32">
      <div className="max-w-[1300px] mx-auto px-6 lg:px-12">
        <div className="text-center mb-16">
          <p className="text-[11px] uppercase tracking-mega text-gold mb-6">
            Your Selection
          </p>
          <h1 className="font-serif text-5xl lg:text-7xl text-ink">Cart</h1>
          <hr className="gold-divider-short mt-10" />
        </div>

        {items.length === 0 ? (
          <div className="text-center py-32" data-testid="empty-cart">
            <p className="font-serif italic text-2xl lg:text-3xl text-ink/60 mb-10">
              Your cart awaits its first fragrance.
            </p>
            <Link to="/fragrances" className="btn-outline-gold">
              Discover the Collection
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-16">
            <div className="lg:col-span-8">
              <hr className="gold-divider mb-10" />
              {items.map((item) => (
                <div
                  key={item.slug}
                  data-testid={`cart-item-${item.slug}`}
                  className="flex gap-6 lg:gap-10 py-10 border-b border-ink/10"
                >
                  <Link
                    to={`/fragrances/${item.slug}`}
                    className="w-28 lg:w-40 shrink-0"
                  >
                    <div className="aspect-square overflow-hidden bg-offwhite">
                      <img
                        src={item.image}
                        alt={item.name}
                        className="w-full h-full object-cover"
                      />
                    </div>
                  </Link>
                  <div className="flex-1 flex flex-col">
                    <p className="text-[10px] uppercase tracking-luxe text-gold mb-2">
                      {item.size} · Eau de Parfum
                    </p>
                    <h3 className="font-serif text-2xl lg:text-3xl text-ink mb-3 tracking-wider">
                      {item.name}
                    </h3>
                    <p className="font-serif text-lg text-ink mb-6">
                      ${item.price.toFixed(2)}
                    </p>
                    <div className="flex items-center justify-between mt-auto">
                      <div className="flex items-center border border-ink/30">
                        <button
                          data-testid={`cart-decrement-${item.slug}`}
                          onClick={() =>
                            updateQty(item.slug, Math.max(1, item.quantity - 1))
                          }
                          className="px-3 py-2 hover:text-gold transition-colors"
                          aria-label="Decrease"
                        >
                          <Minus size={12} strokeWidth={1.25} />
                        </button>
                        <span className="px-5 text-sm tracking-luxe">
                          {item.quantity}
                        </span>
                        <button
                          data-testid={`cart-increment-${item.slug}`}
                          onClick={() => updateQty(item.slug, item.quantity + 1)}
                          className="px-3 py-2 hover:text-gold transition-colors"
                          aria-label="Increase"
                        >
                          <Plus size={12} strokeWidth={1.25} />
                        </button>
                      </div>
                      <button
                        data-testid={`cart-remove-${item.slug}`}
                        onClick={() => removeItem(item.slug)}
                        className="text-ink/60 hover:text-gold transition-colors"
                        aria-label="Remove"
                      >
                        <Trash2 size={16} strokeWidth={1.25} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <aside className="lg:col-span-4">
              <div className="border border-gold/40 p-10 bg-offwhite">
                <p className="text-[11px] uppercase tracking-luxe text-gold mb-6">
                  Summary
                </p>
                <div className="flex justify-between py-3 text-sm font-light">
                  <span>Subtotal</span>
                  <span data-testid="cart-subtotal">
                    ${subtotal.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between py-3 text-sm font-light text-ink/60">
                  <span>Shipping</span>
                  <span>Complimentary</span>
                </div>
                <hr className="gold-divider my-6" />
                <div className="flex justify-between py-3 font-serif text-2xl">
                  <span>Total</span>
                  <span data-testid="cart-total">${subtotal.toFixed(2)}</span>
                </div>
                <button
                  data-testid="checkout-btn"
                  onClick={() => setCheckoutOpen(true)}
                  className="btn-gold w-full mt-8"
                >
                  Reserve by Concierge
                </button>
                <p className="text-[10px] uppercase tracking-luxe text-ink/55 mt-6 text-center leading-[1.8]">
                  Personally handled.<br />
                  Payment arranged after reservation.
                </p>
              </div>
            </aside>
          </div>
        )}

        {checkoutOpen && items.length > 0 && (
          <div
            data-testid="checkout-modal"
            className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center px-6 py-12"
            onClick={() => !submitting && setCheckoutOpen(false)}
          >
            <form
              onClick={(e) => e.stopPropagation()}
              onSubmit={reserve}
              className="bg-cream max-w-xl w-full p-10 lg:p-14 max-h-[90vh] overflow-y-auto"
            >
              <p className="text-[11px] uppercase tracking-mega text-gold mb-6 text-center">
                Concierge Reservation
              </p>
              <h2 className="font-serif text-3xl lg:text-4xl text-ink text-center mb-6">
                Your details
              </h2>
              <p className="text-sm text-ink/70 font-light leading-[1.9] text-center mb-8">
                The maison will write to you within one working day with payment and despatch arrangements.
              </p>
              <hr className="gold-divider-short mx-auto mb-10" />

              <div className="space-y-8">
                <div>
                  <label className="luxe-label">Full Name</label>
                  <input
                    data-testid="checkout-name"
                    className="luxe-input"
                    value={form.customer_name}
                    onChange={update("customer_name")}
                    required
                  />
                </div>
                <div>
                  <label className="luxe-label">Email</label>
                  <input
                    type="email"
                    data-testid="checkout-email"
                    className="luxe-input"
                    value={form.customer_email}
                    onChange={update("customer_email")}
                    required
                  />
                </div>
                <div>
                  <label className="luxe-label">Phone</label>
                  <input
                    type="tel"
                    data-testid="checkout-contact"
                    className="luxe-input"
                    value={form.customer_contact}
                    onChange={update("customer_contact")}
                    placeholder="+91…"
                    required
                  />
                </div>
                <div>
                  <label className="luxe-label">Address Line 1</label>
                  <input
                    data-testid="checkout-address-line1"
                    className="luxe-input"
                    value={form.address_line1}
                    onChange={update("address_line1")}
                    placeholder="Street, building, apartment"
                    required
                  />
                </div>
                <div>
                  <label className="luxe-label">Address Line 2 (optional)</label>
                  <input
                    data-testid="checkout-address-line2"
                    className="luxe-input"
                    value={form.address_line2}
                    onChange={update("address_line2")}
                    placeholder="Landmark, neighbourhood"
                  />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                  <div>
                    <label className="luxe-label">City</label>
                    <input
                      data-testid="checkout-city"
                      className="luxe-input"
                      value={form.city}
                      onChange={update("city")}
                      required
                    />
                  </div>
                  <div>
                    <label className="luxe-label">State</label>
                    <input
                      data-testid="checkout-state"
                      className="luxe-input"
                      value={form.state}
                      onChange={update("state")}
                      required
                    />
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                  <div>
                    <label className="luxe-label">Postal Code</label>
                    <input
                      data-testid="checkout-postal"
                      className="luxe-input"
                      value={form.postal_code}
                      onChange={update("postal_code")}
                      required
                    />
                  </div>
                  <div>
                    <label className="luxe-label">Country</label>
                    <input
                      data-testid="checkout-country"
                      className="luxe-input"
                      value={form.country}
                      onChange={update("country")}
                      required
                    />
                  </div>
                </div>
                <div>
                  <label className="luxe-label">Notes for the maison (optional)</label>
                  <textarea
                    data-testid="checkout-notes"
                    className="luxe-input"
                    rows={3}
                    value={form.notes}
                    onChange={update("notes")}
                    placeholder="Gift wrapping, preferred delivery window, anything else."
                  />
                </div>
              </div>

              <div className="mt-10 pt-8 border-t border-ink/10 flex justify-between">
                <span className="text-[11px] uppercase tracking-luxe text-ink">
                  Reservation Total
                </span>
                <span className="font-serif text-xl">
                  ${subtotal.toFixed(2)}
                </span>
              </div>

              <button
                type="submit"
                data-testid="checkout-submit"
                disabled={submitting}
                className="btn-gold w-full mt-8"
              >
                {submitting ? "Sending reservation…" : "Send Reservation"}
              </button>
              <p className="text-[10px] uppercase tracking-luxe text-ink/55 mt-6 text-center leading-[1.8]">
                No payment is taken now. The maison will reach you within one working day.
              </p>
              <button
                type="button"
                onClick={() => setCheckoutOpen(false)}
                disabled={submitting}
                className="block mx-auto mt-6 text-[11px] uppercase tracking-luxe text-ink/60 hover:text-gold"
              >
                Cancel
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
