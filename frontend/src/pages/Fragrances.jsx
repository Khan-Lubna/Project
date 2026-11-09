
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PRODUCTS } from "../lib/products";
import { USE_SHOPIFY_CATALOG, fetchProducts } from "../lib/shopify";
import FadeSection from "../components/FadeSection";
import { formatPrice } from "../lib/format";

export default function Fragrances() {
  // const [products, setProducts] = useState(() => Object.values(PRODUCTS));

  // useEffect(() => {
  //   if (!USE_SHOPIFY_CATALOG) return;

  //   let active = true;

  //   fetchProducts()
  //     .then((shopifyProducts) => {
  //       if (active && shopifyProducts.length > 0) {
  //         setProducts(shopifyProducts);
  //       }
  //     })
  //     .catch((error) => {
  //       console.error("Unable to load Shopify products:", error);
  //       // Keep the existing static catalogue as a fallback.
  //     });

  //   return () => {
  //     active = false;
  //   };
  // }, []);

  const [products, setProducts] = useState(() =>
    Object.values(PRODUCTS).map((product) => ({
      ...product,
      priceVerified: !USE_SHOPIFY_CATALOG,
    }))
  );

  useEffect(() => {
    if (!USE_SHOPIFY_CATALOG) return;

    let active = true;

    fetchProducts()
      .then((shopifyProducts) => {
        if (!active) return;

        const shopifyMap = new Map(
          shopifyProducts.map((product) => [
            product.slug,
            product.shopify,
          ])
        );

        setProducts(
          Object.values(PRODUCTS).map((product) => {
            const shopifyData = shopifyMap.get(product.slug);

            const selectedVariant = shopifyData?.variants?.find(
              (variant) =>
                variant.availableForSale &&
                variant.currency === "INR" &&
                Number.isFinite(Number(variant.price)) &&
                Number(variant.price) > 0
            );

            if (!selectedVariant) {
              return {
                ...product,
                priceVerified: false,
              };
            }

            return {
              ...product,
              price: Number(selectedVariant.price),
              currency: selectedVariant.currency,
              shopify: shopifyData,
              priceVerified: true,
            };
          })
        );
      })
      .catch((error) => {
        if (!active) return;

        console.error("Unable to verify Shopify product prices:", error);

        setProducts(
          Object.values(PRODUCTS).map((product) => ({
            ...product,
            priceVerified: false,
          }))
        );
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <div data-testid="fragrances-page" className="bg-cream pt-32 lg:pt-44">
      <div className="text-center px-6 mb-20 lg:mb-28">
        <p className="text-[11px] uppercase tracking-mega text-gold mb-6">
          The Collection
        </p>
        <h1 className="font-serif text-5xl lg:text-7xl text-ink leading-tight">
          Two fragrances.<br />
          <span className="italic">One philosophy.</span>
        </h1>
      </div>

      <FadeSection className="grid grid-cols-1 md:grid-cols-2 gap-1 px-1 pb-32">
        {products.map((p) => (
          <Link
            key={p.slug}
            to={`/fragrances/${p.slug}`}
            data-testid={`fragrance-card-${p.slug}`}
            className={`product-card group block ${p.theme === "dark"
              ? "bg-charcoal text-offwhite"
              : "bg-offwhite text-ink"
              }`}
          >
            <div className="aspect-[3/4] overflow-hidden">
              <img
                src={p.image}
                alt={p.name}
                className="product-card-img w-full h-full object-cover"
              />
            </div>

            <div className="px-8 lg:px-12 py-12 text-center">
              <p className="text-[11px] uppercase tracking-luxe text-gold mb-4">
                {p.target} · {p.size}
              </p>
              <h2 className="font-serif text-4xl lg:text-5xl tracking-wider mb-3">
                {p.name}
              </h2>
              <p className="font-serif italic text-lg mb-6 opacity-80">
                {p.tagline}
              </p>
              <p className="text-sm font-light tracking-wider mb-8">
                {p.priceVerified ? (
                  formatPrice(p.price, p.currency)
                ) : (
                  <span className="text-red-700">
                    Price unavailable
                  </span>
                )}
              </p>
              <span className="text-[11px] uppercase tracking-luxe text-gold link-underline">
                Discover
              </span>
            </div>
          </Link>
        ))}
      </FadeSection>
    </div>
  );
}