import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import axios from "axios";
import { PRODUCTS } from "../lib/products";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function QRPayment() {
  const navigate = useNavigate();
  const [selectedSlug, setSelectedSlug] = useState("");
  const [qrUrl, setQrUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [product, setProduct] = useState(null);

  const generateQR = useCallback(async () => {
    if (!selectedSlug) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/qr-code/${encodeURIComponent(selectedSlug)}`);
      setProduct(data.product);
      // The payment_url already embeds the correct product amount — no manual entry needed.
      setQrUrl(data.payment_url);
    } catch (err) {
      toast.error("Failed to generate QR code");
      setQrUrl("");
    } finally {
      setLoading(false);
    }
  }, [selectedSlug]);

  useEffect(() => {
    if (selectedSlug) {
      void generateQR();
    }
  }, [selectedSlug]);

  return (
    <div className="min-h-screen bg-cream pt-32 lg:pt-44 pb-32">
      <div className="max-w-2xl mx-auto px-6">
        <div className="text-center mb-12">
          <p className="text-[11px] uppercase tracking-mega text-gold mb-6">
            Razorpay QR
          </p>
          <h1 className="font-serif text-4xl lg:text-5xl text-ink">
            Pay by QR Code
          </h1>
          <p className="text-sm text-ink/60 font-light mt-4 max-w-md mx-auto leading-relaxed">
            Pick a fragrance below. Razorpay generates a QR whose amount is
            already pre-filled — the customer only needs to scan and confirm.
          </p>
          <hr className="gold-divider-short mt-8" />
        </div>

        <div className="border border-gold/40 p-8 lg:p-10 bg-offwhite">
          <label className="luxe-label mb-3 block">Select Fragrance</label>
          <select
            value={selectedSlug}
            onChange={(e) => {
              setSelectedSlug(e.target.value);
              setQrUrl("");
              setProduct(null);
            }}
            className="luxe-input mb-8"
          >
            <option value="">— Choose a fragrance —</option>
            {Object.values(PRODUCTS).map((p) => (
              <option key={p.slug} value={p.slug}>
                {p.name} — ${p.price.toFixed(2)} USD
              </option>
            ))}
          </select>

          {loading && (
            <div className="text-center py-12">
              <p className="text-gold tracking-luxe">Generating QR…</p>
            </div>
          )}

          {qrUrl && product && !loading && (
            <div className="text-center">
              <p className="text-[10px] uppercase tracking-luxe text-gold mb-4">
                {product.name} — {product.slug}
              </p>
              <p className="font-serif text-3xl text-ink mb-6">
                ${product.price.toFixed(2)} USD
              </p>
              <p className="text-[10px] uppercase tracking-luxe text-ink/60 mb-6">
                Amount is pre-filled — scan to pay instantly
              </p>
              <div className="inline-block p-4 bg-white border border-ink/10 rounded-sm">
                <img
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=260x260&data=${encodeURIComponent(qrUrl)}`}
                  alt={`QR code for ${product.name}`}
                  className="w-[260px] h-[260px]"
                />
              </div>
              <p className="text-[11px] text-ink/60 mt-6">
                Opens Razorpay&apos;s payment page with{" "}
                <strong className="text-ink">${product.price.toFixed(2)}</strong> already entered.
              </p>
              <button
                onClick={() => navigate(-1)}
                className="btn-outline-gold w-full mt-8"
              >
                ← Back
              </button>
            </div>
          )}

          {!qrUrl && !loading && (
            <p className="text-[11px] text-ink/50 text-center py-4">
              Select a fragrance above to generate its payment QR code.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
