import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import axios from "axios";
import { useCart } from "../context/CartContext";
import { PRODUCTS } from "../lib/products";
import { loadRazorpay } from "../lib/razorpay";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function QRCheckout() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [processing, setProcessing] = useState(false);
  const [pin, setPin] = useState("");
  const [product, setProduct] = useState(null);
  const [slug, setSlug] = useState(null);
  const { clear } = useCart();

  useEffect(() => {
    const productSlug = searchParams.get("product");
    if (productSlug && PRODUCTS[productSlug]) {
      setSlug(productSlug);
      setProduct(PRODUCTS[productSlug]);
    } else {
      toast.error("Invalid product");
      navigate("/");
    }
  }, [searchParams, navigate]);

  const handlePinSubmit = async (e) => {
    e.preventDefault();
    if (pin.length !== 4) {
      toast.error("Please enter a valid 4-digit PIN");
      return;
    }

    setProcessing(true);

    try {
      const { data } = await axios.post(`${API}/qr-checkout`, {
        slug,
        pin,
      });

      const Razorpay = await loadRazorpay();
      const options = {
        key: process.env.REACT_APP_RAZORPAY_KEY_ID,
        amount: data.amount,
        currency: "USD",
        name: "Mossero",
        description: `${product.name} - QR Express Checkout`,
        order_id: data.order_id,
        handler: async function (response) {
          try {
            // Verify payment server-side via signature
            await axios.post(`${API}/checkout/verify`, {
              order_id: data.order_id,
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            });
          } catch (verifyErr) {
            // If verify fails, the webhook will still pick it up — show error but note recovery path.
            toast.warning(
              verifyErr?.response?.data?.detail ||
                "Payment detection delayed; confirmation will follow shortly."
            );
          }
          clear();
          toast.success("Payment successful!");
          navigate(
            `/cart/success?order_id=${data.order_id}&mode=qr-express`
          );
        },
        prefill: {
          name: "",
          email: "",
          contact: "",
        },
        theme: {
          color: "#C4A258",
        },
        modal: {
          ondismiss: function () {
            setProcessing(false);
          },
        },
      };
      new Razorpay(options).open();
    } catch (err) {
      toast.error("Payment failed. Please try again.");
      setProcessing(false);
    }
  };

  if (!product) {
    return (
      <div className="min-h-screen bg-cream pt-32 lg:pt-44 pb-32 flex items-center justify-center">
        <p className="text-ink">Loading...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-cream pt-32 lg:pt-44 pb-32">
      <div className="max-w-2xl mx-auto px-6">
        <div className="text-center mb-12">
          <p className="text-[11px] uppercase tracking-mega text-gold mb-6">
            QR Express Checkout
          </p>
          <h1 className="font-serif text-4xl lg:text-5xl text-ink">
            Complete Payment
          </h1>
          <hr className="gold-divider-short mt-8" />
        </div>

        <div className="border border-gold/40 p-8 bg-offwhite">
          <div className="text-center mb-8">
            <img
              src={product.image}
              alt={product.name}
              className="w-24 h-24 object-cover mx-auto mb-4"
            />
            <h2 className="font-serif text-2xl text-ink">{product.name}</h2>
            <p className="text-lg font-serif text-gold">${product.price.toFixed(2)}</p>
          </div>

          <form onSubmit={handlePinSubmit}>
            <div className="mb-6">
              <label className="luxe-label text-center block">Enter 4-digit PIN</label>
              <input
                type="password"
                maxLength={4}
                value={pin}
                onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
                className="luxe-input w-32 mx-auto block text-center text-2xl tracking-[0.5em]"
                inputMode="numeric"
                pattern="[0-9]{4}"
                required
              />
            </div>

            <button
              type="submit"
              disabled={processing || pin.length !== 4}
              className="btn-gold w-full"
            >
              {processing ? "Processing..." : `Pay $${product.price.toFixed(2)}`}
            </button>
          </form>

          <button
            onClick={() => navigate("/")}
            disabled={processing}
            className="block mx-auto mt-4 text-[11px] uppercase tracking-luxe text-ink/60 hover:text-gold"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}