import { Link } from "react-router-dom";
import { PRODUCTS } from "../lib/products";
import FadeSection from "../components/FadeSection";
import { formatPrice } from "../lib/format";

export default function Fragrances() {
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
        {Object.values(PRODUCTS).map((p) => (
          <Link
            key={p.slug}
            to={`/fragrances/${p.slug}`}
            data-testid={`fragrance-card-${p.slug}`}
            className={`product-card group block ${p.theme === "dark" ? "bg-charcoal text-offwhite" : "bg-offwhite text-ink"
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
                {formatPrice(p.price, p.currency)}
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