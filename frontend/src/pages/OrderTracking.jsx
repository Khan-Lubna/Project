import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import FadeSection from "../components/FadeSection";
import { formatPrice } from "../lib/format";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_COPY = {
  paid: { label: "Payment Confirmed", next: "Your fragrance is being prepared for despatch." },
  initiated: { label: "Awaiting Payment", next: "We have not yet received payment for this order." },
  failed: { label: "Payment Failed", next: "Please return to your cart and try again." },
  preparing: { label: "Preparing for Despatch", next: "Your order is being prepared by the atelier." },
  awaiting_payment: { label: "Awaiting Payment", next: "Payment has not yet been received." },
  fulfillment_pending: { label: "Awaiting Fulfilment", next: "Your order is paid and queued for the courier — a tracking number will appear here shortly." },
  dispatched: { label: "Dispatched", next: "Your fragrance has left the atelier and is on its way." },
  in_transit: { label: "In Transit", next: "Your order is travelling to you." },
  out_for_delivery: { label: "Out for Delivery", next: "Your fragrance is with the courier and arrives today." },
  concierge_pending: {
    label: "Reservation Pending",
    next: "The maison will contact you within one working day with payment and despatch details.",
  },
  delivered: { label: "Delivered", next: "Your fragrance has arrived. We hope you love it." },
};

export default function OrderTracking() {
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState({
    order_id: searchParams.get("order_id") || "",
    email: "",
  });
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(false);

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const lookup = async (e) => {
    e.preventDefault();
    if (!form.order_id || !form.email) {
      toast.error("Please enter both your order reference and email.");
      return;
    }
    setLoading(true);
    setOrder(null);
    try {
      const res = await axios.post(`${API}/orders/lookup`, {
        order_id: form.order_id.trim().toUpperCase(),
        email: form.email.trim(),
      });
      setOrder(res.data);
    } catch (err) {
      const msg =
        err?.response?.status === 404
          ? "No order found with that reference and email."
          : err?.response?.data?.detail || "Unable to look up order.";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setOrder(null);
    setForm({ order_id: "", email: "" });
  };

  return (
    <div data-testid="track-page" className="bg-cream pt-32 lg:pt-44 pb-32">
      <div className="max-w-[900px] mx-auto px-6 lg:px-12">
        <div className="text-center mb-16">
          <p className="text-[11px] uppercase tracking-mega text-gold mb-6">
            Order Tracking
          </p>
          <h1 className="font-serif text-5xl lg:text-7xl text-ink leading-tight">
            Follow your <span className="italic">fragrance.</span>
          </h1>
          <hr className="gold-divider-short mt-10" />
        </div>

        {!order && (
          <FadeSection>
            <form
              data-testid="track-form"
              onSubmit={lookup}
              className="border border-gold/40 bg-offwhite p-10 lg:p-14 space-y-8 max-w-xl mx-auto"
            >
              <p className="text-sm text-ink/70 leading-[1.9] font-light text-center">
                Enter your order reference (begins with{" "}
                <span className="font-medium text-ink">MSR-</span>) and the
                email used at checkout.
              </p>
              <div>
                <label className="luxe-label">Order Reference</label>
                <input
                  data-testid="track-order-id"
                  className="luxe-input"
                  placeholder="MSR-XXXXXXXX"
                  value={form.order_id}
                  onChange={update("order_id")}
                  required
                />
              </div>
              <div>
                <label className="luxe-label">Email</label>
                <input
                  type="email"
                  data-testid="track-email"
                  className="luxe-input"
                  value={form.email}
                  onChange={update("email")}
                  required
                />
              </div>
              <button
                type="submit"
                data-testid="track-submit"
                disabled={loading}
                className="btn-gold w-full"
              >
                {loading ? "Looking up…" : "Track Order"}
              </button>
            </form>
          </FadeSection>
        )}

        {order && (
          <FadeSection data-testid="track-result">
            <div className="border border-gold/40 bg-offwhite p-10 lg:p-14">
              <div className="text-center mb-12">
                <p className="text-[11px] uppercase tracking-mega text-gold mb-4">
                  {STATUS_COPY[order.shipping_status]?.label ||
                    STATUS_COPY[order.payment_status]?.label ||
                    "Order Found"}
                </p>
                <h2
                  className="font-serif text-3xl lg:text-5xl text-ink tracking-wider"
                  data-testid="track-order-ref"
                >
                  Order {order.order_id}
                </h2>
                <hr className="gold-divider-short mx-auto mt-8" />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-10 mb-12">
                <div>
                  <p className="text-[10px] uppercase tracking-luxe text-ink mb-2">
                    Status
                  </p>
                  <p
                    className="font-serif text-xl text-ink mb-1"
                    data-testid="track-status"
                  >
                    {STATUS_COPY[order.shipping_status]?.label ||
                      STATUS_COPY[order.payment_status]?.label ||
                      order.payment_status}
                  </p>
                  <p className="text-sm text-ink/65 font-light leading-[1.8]">
                    {STATUS_COPY[order.shipping_status]?.next ||
                      STATUS_COPY[order.payment_status]?.next ||
                      ""}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-luxe text-ink mb-2">
                    Customer
                  </p>
                  <p className="text-sm text-ink mb-3">{order.customer_name}</p>
                  <p className="text-[10px] uppercase tracking-luxe text-ink mb-2">
                    Placed
                  </p>
                  <p className="text-sm text-ink/65 font-light">
                    {new Date(order.created_at).toLocaleString()}
                  </p>
                </div>
              </div>

              <hr className="gold-divider mb-8" />

              {(order.courier_name || order.awb_number || order.tracking) && (
                <div
                  data-testid="track-shiprocket-block"
                  className="bg-cream border border-gold/40 p-6 lg:p-8 mb-10"
                >
                  <p className="text-[10px] uppercase tracking-luxe text-gold mb-4">
                    Courier
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                    {order.courier_name && (
                      <div>
                        <p className="text-[10px] uppercase tracking-luxe text-ink/60 mb-1">
                          Partner
                        </p>
                        <p
                          className="font-serif text-lg text-ink"
                          data-testid="track-courier"
                        >
                          {order.courier_name}
                        </p>
                      </div>
                    )}
                    {order.awb_number && (
                      <div>
                        <p className="text-[10px] uppercase tracking-luxe text-ink/60 mb-1">
                          AWB
                        </p>
                        <p
                          className="font-mono text-sm text-ink"
                          data-testid="track-awb"
                        >
                          {order.awb_number}
                        </p>
                      </div>
                    )}
                    {order.tracking?.estimated_delivery && (
                      <div>
                        <p className="text-[10px] uppercase tracking-luxe text-ink/60 mb-1">
                          ETA
                        </p>
                        <p className="text-sm text-ink">
                          {order.tracking.estimated_delivery}
                        </p>
                      </div>
                    )}
                  </div>
                  {order.tracking?.current_location && (
                    <p className="text-sm text-ink/70 font-light mt-5">
                      Currently at{" "}
                      <span className="text-ink">
                        {order.tracking.current_location}
                      </span>
                    </p>
                  )}
                  {order.tracking_url && (
                    <a
                      href={order.tracking_url}
                      target="_blank"
                      rel="noreferrer"
                      data-testid="track-external-url"
                      className="inline-block mt-6 text-[10px] uppercase tracking-luxe text-gold link-underline"
                    >
                      View on courier site →
                    </a>
                  )}
                </div>
              )}

              <p className="text-[10px] uppercase tracking-luxe text-ink mb-6">
                Items
              </p>
              <ul className="space-y-4 mb-10">
                {order.items.map((it) => {
                  const line =
                    typeof it.line_total === "number"
                      ? it.line_total
                      : (it.unit_price || 0) * (it.quantity || 0);
                  return (
                    <li
                      key={it.slug}
                      data-testid={`track-item-${it.slug}`}
                      className="flex justify-between items-baseline"
                    >
                      <div>
                        <p className="font-serif text-xl text-ink tracking-wider">
                          {it.name}
                        </p>
                        <p className="text-[10px] uppercase tracking-luxe text-ink/60 mt-1">
                          50ml × {it.quantity}
                        </p>
                      </div>
                      <p className="font-serif text-lg text-ink">
                        {formatPrice(line, order.currency)}
                      </p>
                    </li>
                  );
                })}
              </ul>

              <div className="flex justify-between items-baseline border-t border-ink/15 pt-6 mb-10">
                <span className="text-[11px] uppercase tracking-luxe text-ink">
                  Total
                </span>
                <span
                  className="font-serif text-2xl text-ink"
                  data-testid="track-total"
                >
                  {formatPrice(order.total ?? 0, order.currency || "INR")}
                </span>
              </div>

              <div className="mb-10">
                <p className="text-[10px] uppercase tracking-luxe text-ink mb-3">
                  Shipping to
                </p>
                <p
                  className="text-sm text-ink/75 font-light leading-[1.9] whitespace-pre-line"
                  data-testid="track-shipping"
                >
                  {order.shipping_address}
                </p>
              </div>

              <div className="flex flex-col sm:flex-row gap-4 justify-center pt-6 border-t border-ink/15">
                <button
                  type="button"
                  onClick={reset}
                  data-testid="track-lookup-another"
                  className="btn-outline-gold"
                >
                  Track Another Order
                </button>
                <Link to="/contact" className="btn-outline-gold">
                  Contact the Maison
                </Link>
              </div>
            </div>
          </FadeSection>
        )}
      </div>
    </div>
  );
}
