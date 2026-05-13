import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import axios from "axios";
import { useCart } from "../context/CartContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_ATTEMPTS = 8;

export default function CheckoutSuccess() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const { clear } = useCart();
  const [state, setState] = useState({
    status: "polling",
    payment_status: null,
    order_id: null,
    amount_total: null,
    currency: null,
    error: null,
  });
  const attemptsRef = useRef(0);
  const clearedRef = useRef(false);

  useEffect(() => {
    if (!sessionId) {
      setState((s) => ({ ...s, status: "error", error: "Missing session id" }));
      return;
    }

    let cancelled = false;

    const poll = async () => {
      if (cancelled) return;
      attemptsRef.current += 1;
      try {
        const res = await axios.get(`${API}/checkout/status/${sessionId}`);
        const data = res.data;
        if (data.payment_status === "paid") {
          if (!clearedRef.current) {
            clear();
            clearedRef.current = true;
            sessionStorage.removeItem("mossero_pending_session");
          }
          setState({
            status: "paid",
            payment_status: "paid",
            order_id: data.order_id,
            amount_total: data.amount_total,
            currency: data.currency,
            error: null,
          });
          return;
        }
        if (data.status === "expired") {
          setState({
            status: "expired",
            payment_status: data.payment_status,
            order_id: data.order_id,
            amount_total: data.amount_total,
            currency: data.currency,
            error: null,
          });
          return;
        }
        if (attemptsRef.current >= MAX_POLL_ATTEMPTS) {
          setState({
            status: "timeout",
            payment_status: data.payment_status,
            order_id: data.order_id,
            amount_total: data.amount_total,
            currency: data.currency,
            error: null,
          });
          return;
        }
        setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        setState((s) => ({
          ...s,
          status: "error",
          error: err?.response?.data?.detail || "Unable to verify payment.",
        }));
      }
    };

    poll();
    return () => {
      cancelled = true;
    };
  }, [sessionId, clear]);

  if (state.status === "polling") {
    return (
      <div
        data-testid="checkout-success-polling"
        className="bg-cream pt-40 pb-40 px-6 text-center"
      >
        <p className="text-[11px] uppercase tracking-mega text-gold mb-8">
          Confirming
        </p>
        <h1 className="font-serif text-4xl lg:text-6xl text-ink leading-tight mb-8">
          Verifying your payment…
        </h1>
        <hr className="gold-divider-short mb-10 mx-auto" />
        <p className="text-base text-ink/70 font-light max-w-xl mx-auto leading-[1.9]">
          A moment, please. We are confirming your transaction with Stripe.
        </p>
      </div>
    );
  }

  if (state.status === "paid") {
    const formatted =
      state.amount_total != null
        ? (state.amount_total / 100).toFixed(2)
        : null;
    return (
      <div
        data-testid="order-confirmation"
        className="bg-cream pt-40 pb-40 px-6 text-center"
      >
        <p className="text-[11px] uppercase tracking-mega text-gold mb-8">
          Confirmation
        </p>
        <h1 className="font-serif text-5xl lg:text-7xl text-ink leading-tight mb-8">
          Thank you.
        </h1>
        <hr className="gold-divider-short mb-10 mx-auto" />
        <p className="text-base text-ink/70 font-light max-w-xl mx-auto leading-[1.9] mb-6">
          Your order has been received and your payment confirmed.
          A discreet email confirmation will follow shortly.
        </p>
        {state.order_id && (
          <p className="text-sm tracking-luxe text-ink mb-2" data-testid="order-id">
            Order #{state.order_id}
          </p>
        )}
        {formatted && (
          <p className="font-serif text-2xl text-ink mb-12">
            Total ${formatted} {state.currency?.toUpperCase()}
          </p>
        )}
        <Link to="/fragrances" className="btn-outline-gold">
          Return to the Collection
        </Link>
      </div>
    );
  }

  if (state.status === "expired") {
    return (
      <div
        data-testid="checkout-expired"
        className="bg-cream pt-40 pb-40 px-6 text-center"
      >
        <p className="text-[11px] uppercase tracking-mega text-gold mb-8">
          Session expired
        </p>
        <h1 className="font-serif text-4xl lg:text-6xl text-ink leading-tight mb-8">
          Your checkout session has expired.
        </h1>
        <hr className="gold-divider-short mb-10 mx-auto" />
        <Link to="/cart" className="btn-outline-gold">
          Return to Cart
        </Link>
      </div>
    );
  }

  if (state.status === "timeout") {
    return (
      <div
        data-testid="checkout-timeout"
        className="bg-cream pt-40 pb-40 px-6 text-center"
      >
        <p className="text-[11px] uppercase tracking-mega text-gold mb-8">
          Still processing
        </p>
        <h1 className="font-serif text-4xl lg:text-6xl text-ink leading-tight mb-8">
          Your payment is still being processed.
        </h1>
        <hr className="gold-divider-short mb-10 mx-auto" />
        <p className="text-base text-ink/70 font-light max-w-xl mx-auto leading-[1.9] mb-10">
          You will receive a confirmation by email as soon as it is verified.
        </p>
        <Link to="/" className="btn-outline-gold">
          Return Home
        </Link>
      </div>
    );
  }

  return (
    <div
      data-testid="checkout-error"
      className="bg-cream pt-40 pb-40 px-6 text-center"
    >
      <p className="text-[11px] uppercase tracking-mega text-gold mb-8">
        Something went wrong
      </p>
      <h1 className="font-serif text-4xl lg:text-6xl text-ink leading-tight mb-8">
        We could not verify your payment.
      </h1>
      <hr className="gold-divider-short mb-10 mx-auto" />
      <p className="text-base text-ink/70 font-light max-w-xl mx-auto leading-[1.9] mb-10">
        {state.error ||
          "Please try again, or contact us if you have been charged."}
      </p>
      <Link to="/cart" className="btn-outline-gold">
        Return to Cart
      </Link>
    </div>
  );
}
