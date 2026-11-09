import { useEffect, useState } from "react";
import { useParams, Navigate, Link, useNavigate } from "react-router-dom";
import { Minus, Plus } from "lucide-react";
import { toast } from "sonner";
import { PRODUCTS } from "../lib/products";
import { useCart } from "../context/CartContext";
import FadeSection from "../components/FadeSection";
import { formatPrice } from "../lib/format";
import {
  USE_SHOPIFY_CATALOG,
  fetchProductByHandle,
} from "../lib/shopify";


export default function Product() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { addItem } = useCart();

  const staticProduct = PRODUCTS[slug];

  const [productState, setProductState] = useState(() => ({
    slug,
    product: staticProduct || null,
    loading: USE_SHOPIFY_CATALOG,
    priceVerified: !USE_SHOPIFY_CATALOG,
  }));

  const [qty, setQty] = useState(1);

  useEffect(() => {
    let active = true;
    const fallback = PRODUCTS[slug] || null;

    setProductState({
      slug,
      product: fallback,
      loading: USE_SHOPIFY_CATALOG,
      priceVerified: !USE_SHOPIFY_CATALOG,
    });

    if (!USE_SHOPIFY_CATALOG) {
      return () => {
        active = false;
      };
    }

    fetchProductByHandle(slug)
      .then((shopifyProduct) => {
        if (!active) return;

        if (!shopifyProduct?.shopify?.variants?.length) {
          throw new Error("Shopify product or variants are unavailable.");
        }

        const selectedVariant =
          shopifyProduct.shopify.variants.find(
            (variant) =>
              variant.availableForSale &&
              variant.currency === "INR" &&
              Number.isFinite(Number(variant.price)) &&
              Number(variant.price) > 0
          );

        if (!selectedVariant) {
          throw new Error("No available Shopify variant with a valid INR price.");
        }

        setProductState({
          slug,
          product: {
            ...fallback,
            ...shopifyProduct,
            price: Number(selectedVariant.price),
            currency: selectedVariant.currency,
          },
          loading: false,
          priceVerified: true,
        });
      })
      .catch((error) => {
        if (!active) return;

        console.error("Unable to verify Shopify product price:", error);

        setProductState({
          slug,
          product: fallback,
          loading: false,
          priceVerified: false,
        });
      });

    return () => {
      active = false;
    };
  }, [slug]);

  const product =
    productState.slug === slug
      ? productState.product
      : staticProduct || null;

  const isLoading =
    productState.slug === slug && productState.loading;

  if (isLoading && !product) {
    return (
      <div className="bg-cream min-h-screen pt-32 text-center">
        Loading fragrance...
      </div>
    );
  }

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

  const priceVerified =
    productState.slug === slug && productState.priceVerified;

  const handleAdd = () => {
    if (USE_SHOPIFY_CATALOG && !priceVerified) {
      toast.error("Product price could not be verified", {
        description: "Please try again later.",
      });
      return;
    }

    addItem(product, qty);

    toast.success(`${product.name} added to your cart`, {
      description: `${qty} × ${product.size} Eau de Parfum`,
    });
  };

  const handleBuyNow = () => {
    if (USE_SHOPIFY_CATALOG && !priceVerified) {
      toast.error("Product price could not be verified", {
        description: "Please try again later.",
      });
      return;
    }

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
            className={`font-serif text-6xl sm:text-7xl lg:text-9xl tracking-wider ${isDark ? "text-offwhite" : "text-ink"
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
            {priceVerified ? (
              <p className="font-serif text-2xl mb-10">
                {formatPrice(product.price, product.currency)}
              </p>
            ) : (
              <p className="font-serif text-xl mb-10">
                {isLoading ? "Verifying price..." : "Price unavailable"}
              </p>
            )}
            {USE_SHOPIFY_CATALOG && !priceVerified && (
              <p className="text-sm text-red-700 mb-6">
                {isLoading
                  ? "Verifying latest price..."
                  : "Price currently unavailable. Please try again later."}
              </p>
            )}

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
              className="btn-gold w-full mb-4 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={USE_SHOPIFY_CATALOG && !priceVerified}
            >
              Add to Cart
            </button>
            <button
              data-testid="buy-now-btn"
              onClick={handleBuyNow}
              className={`${isDark ? "btn-outline-light" : "btn-outline-gold"} w-full disabled:opacity-50 disabled:cursor-not-allowed`}
              disabled={USE_SHOPIFY_CATALOG && !priceVerified}
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
                className={`px-8 py-16 text-center border ${palette.border} ${i === 1 ? "md:border-l-0 md:border-r-0" : ""
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