import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function CheckoutSuccess() {
  const [searchParams] = useSearchParams();
  const orderId = searchParams.get("order_id");
  const verifyFlag = searchParams.get("verify");
  const [state, setState] = useState({
    loading: true,
    payment_status: null,
    amount_total: null,
    currency: null,
    error: verifyFlag === "failed" ? "Payment verification failed." : null,
  });

  useEffect(() => {
    if (!orderId) {
      setState({ loading: false, error: "Missing order id" });
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API}/checkout/status/${orderId}`);
        if (cancelled) return;
        setState({
          loading: false,
          payment_status: res.data.payment_status,
          amount_total: res.data.amount_total,
          currency: res.data.currency,
          error: null,
        });
      } catch (err) {
        if (cancelled) return;
        setState({
          loading: false,
          error: err?.response?.data?.detail || "Unable to load order.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [orderId]);

  if (state.loading) {
    return (
      <div
        data-testid="checkout-success-loading"
        className="bg-cream pt-40 pb-40 px-6 text-center"
      >
        <p className="text-[11px] uppercase tracking-mega text-gold mb-8">
          Confirming
        </p>
        <h1 className="font-serif text-4xl lg:text-6xl text-ink leading-tight">
          Loading your order…
        </h1>
      </div>
    );
  }

  if (state.error || state.payment_status === "failed") {
    return (
      <div
        data-testid="checkout-error"
        className="bg-cream pt-40 pb-40 px-6 text-center"
      >
        <p className="text-[11px] uppercase tracking-mega text-gold mb-8">
          Payment issue
        </p>
        <h1 className="font-serif text-4xl lg:text-6xl text-ink leading-tight mb-8">
          Something went wrong.
        </h1>
        <hr className="gold-divider-short mb-10 mx-auto" />
        <p className="text-base text-ink/70 font-light max-w-xl mx-auto leading-[1.9] mb-10">
          {state.error ||
            "Your payment was not successful. If you have been charged, please contact us at mossero.in@gmail.com and we will resolve it within hours."}
        </p>
        {orderId && (
          <p
            className="text-sm tracking-luxe text-ink/60 mb-10"
            data-testid="order-id"
          >
            Reference #{orderId}
          </p>
        )}
        <Link to="/cart" className="btn-outline-gold">
          Return to Cart
        </Link>
      </div>
    );
  }

  if (state.payment_status === "paid") {
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
          Your order has been received and your payment confirmed. A discreet
          email confirmation will follow shortly.
        </p>
        <p className="text-sm tracking-luxe text-ink mb-2" data-testid="order-id">
          Order #{orderId}
        </p>
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

  // initiated / open / unknown — pending state
  return (
    <div
      data-testid="checkout-pending"
      className="bg-cream pt-40 pb-40 px-6 text-center"
    >
      <p className="text-[11px] uppercase tracking-mega text-gold mb-8">
        Pending
      </p>
      <h1 className="font-serif text-4xl lg:text-6xl text-ink leading-tight mb-8">
        Your payment is being processed.
      </h1>
      <hr className="gold-divider-short mb-10 mx-auto" />
      <p className="text-base text-ink/70 font-light max-w-xl mx-auto leading-[1.9] mb-10">
        You will receive a confirmation by email as soon as it is verified.
      </p>
      {orderId && (
        <p
          className="text-sm tracking-luxe text-ink/60 mb-10"
          data-testid="order-id"
        >
          Order #{orderId}
        </p>
      )}
      <Link to="/" className="btn-outline-gold">
        Return Home
      </Link>
    </div>
  );
}
