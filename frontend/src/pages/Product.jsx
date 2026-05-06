import { useState } from "react";
import { useParams, Navigate, Link, useNavigate } from "react-router-dom";
import { Minus, Plus } from "lucide-react";
import { toast } from "sonner";
import { PRODUCTS } from "../lib/products";
import { useCart } from "../context/CartContext";
import FadeSection from "../components/FadeSection";

export default function Product() {
  const { slug } = useParams();
  const product = PRODUCTS[slug];
  const navigate = useNavigate();
  const { addItem } = useCart();
  const [qty, setQty] = useState(1);

  if (!product) return <Navigate to="/fragrances" replace />;

  const isDark = product.theme === "dark";

  const palette = isDark
    ? {
        bg: "bg-charcoal",
        text: "text-offwhite",
        soft: "text-offwhite/70",
        border: "border-offwhite/20",
        cardBg: "bg-charcoal",
        priceBg: "bg-charcoal",
      }
    : {
        bg: "bg-offwhite",
        text: "text-ink",
        soft: "text-ink/70",
        border: "border-ink/20",
        cardBg: "bg-offwhite",
        priceBg: "bg-offwhite",
      };

  const handleAdd = () => {
    addItem(product, qty);
    toast.success(`${product.name} added to your cart`, {
      description: `${qty} × ${product.size} Eau de Parfum`,
    });
  };

  const handleBuyNow = () => {
    addItem(product, qty);
    navigate("/cart");
  };

  return (
    <div data-testid={`product-page-${product.slug}`} className={`${palette.bg} ${palette.text}`}>
      {/* HERO */}
      <section className="relative h-[80vh] min-h-[640px] w-full overflow-hidden pt-24">
        <img
          src={product.image}
          alt={product.name}
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className={`absolute inset-0 ${isDark ? "bg-black/40" : "bg-white/10"}`} />
        <div className="relative h-full flex flex-col items-center justify-end text-center pb-20 px-6">
          <p className="text-[11px] uppercase tracking-mega text-gold mb-6">
            {product.target} · {product.type}
          </p>
          <h1
            data-testid="product-name"
            className={`font-serif text-6xl sm:text-7xl lg:text-9xl tracking-wider ${
              isDark ? "text-offwhite" : "text-ink"
            }`}
          >
            {product.name}
          </h1>
          <p className={`font-serif italic text-xl lg:text-2xl mt-4 ${palette.soft}`}>
            {product.tagline}
          </p>
        </div>
      </section>

      {/* DESCRIPTION + BUY */}
      <section className="max-w-[1400px] mx-auto px-6 lg:px-12 py-24 lg:py-32 grid grid-cols-1 lg:grid-cols-12 gap-16">
        <div className="lg:col-span-7">
          <p className="text-[11px] uppercase tracking-luxe text-gold mb-6">
            The Composition
          </p>
          <h2 className="font-serif text-3xl lg:text-5xl leading-tight mb-10">
            A fragrance built<br />
            <span className="italic">for the long hours.</span>
          </h2>
          <hr className="gold-divider-short mb-10" />
          <p className={`text-base leading-[1.9] font-light max-w-xl ${palette.soft}`}>
            {product.description}
          </p>
        </div>

        <div className="lg:col-span-5 lg:pl-10">
          <div className={`border ${palette.border} p-10 lg:p-12`}>
            <p className="text-[11px] uppercase tracking-luxe text-gold mb-3">
              {product.size} · {product.type}
            </p>
            <h3 className="font-serif text-3xl lg:text-4xl mb-8 tracking-wider">
              {product.name}
            </h3>
            <p className="font-serif text-2xl mb-10">${product.price.toFixed(2)} USD</p>

            <p className="luxe-label" style={{ color: isDark ? "#FBF7F2" : undefined }}>
              Quantity
            </p>
            <div className={`flex items-center border ${palette.border} w-fit mb-10`}>
              <button
                data-testid="qty-decrement"
                onClick={() => setQty(Math.max(1, qty - 1))}
                className="px-4 py-3 hover:text-gold transition-colors"
                aria-label="Decrease"
              >
                <Minus size={14} strokeWidth={1.25} />
              </button>
              <span
                data-testid="qty-value"
                className="px-6 py-3 text-sm tracking-luxe min-w-[60px] text-center"
              >
                {qty}
              </span>
              <button
                data-testid="qty-increment"
                onClick={() => setQty(Math.min(20, qty + 1))}
                className="px-4 py-3 hover:text-gold transition-colors"
                aria-label="Increase"
              >
                <Plus size={14} strokeWidth={1.25} />
              </button>
            </div>

            <button
              data-testid="add-to-cart-btn"
              onClick={handleAdd}
              className="btn-gold w-full mb-4"
            >
              Add to Cart
            </button>
            <button
              data-testid="buy-now-btn"
              onClick={handleBuyNow}
              className={isDark ? "btn-outline-light w-full" : "btn-outline-gold w-full"}
            >
              Buy Now
            </button>
          </div>
        </div>
      </section>

      {/* NOTES */}
      <FadeSection className={`${isDark ? "bg-charcoal" : "bg-cream"} py-24 lg:py-36 border-t ${palette.border}`}>
        <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
          <div className="text-center mb-20">
            <p className="text-[11px] uppercase tracking-mega text-gold mb-6">
              Olfactive Pyramid
            </p>
            <h3 className="font-serif text-4xl lg:text-6xl">
              The notes, in <span className="italic">three movements.</span>
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-1">
            {[
              { label: "Top Notes", values: product.notes.top },
              { label: "Heart Notes", values: product.notes.heart },
              { label: "Base Notes", values: product.notes.base },
            ].map((group, i) => (
              <div
                key={group.label}
                data-testid={`notes-${group.label.toLowerCase().replace(/\s+/g, "-")}`}
                className={`px-8 py-16 text-center border ${palette.border} ${
                  i === 1 ? "md:border-l-0 md:border-r-0" : ""
                }`}
              >
                <p className="text-[10px] uppercase tracking-mega text-gold mb-8">
                  {group.label}
                </p>
                <ul className="space-y-3">
                  {group.values.map((n) => (
                    <li
                      key={n}
                      className="font-serif text-2xl lg:text-3xl italic"
                    >
                      {n}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </FadeSection>

      {/* STORY EXCERPT */}
      <FadeSection className={`${palette.bg} py-24 lg:py-32`}>
        <div className="max-w-3xl mx-auto px-6 text-center">
          <p className="text-[11px] uppercase tracking-mega text-gold mb-8">
            From the Maison
          </p>
          <p className={`font-serif text-2xl lg:text-4xl leading-snug italic ${palette.soft}`}>
            “Mo-SEH-ro. From moss — quiet, enduring, alive.”
          </p>
          <div className="mt-12">
            <Link
              to="/our-story"
              data-testid="product-story-link"
              className={isDark ? "btn-outline-light" : "btn-outline-gold"}
            >
              Read Our Story
            </Link>
          </div>
        </div>
      </FadeSection>
    </div>
  );
}
