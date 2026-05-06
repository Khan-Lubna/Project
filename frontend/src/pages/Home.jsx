import { Link } from "react-router-dom";
import FadeSection from "../components/FadeSection";
import { PRODUCTS, HERO_IMAGE, STORY_IMAGE, INSTAGRAM_GRID } from "../lib/products";

export default function Home() {
  return (
    <div data-testid="home-page">
      {/* HERO */}
      <section className="relative h-screen min-h-[700px] w-full overflow-hidden">
        <img
          src={HERO_IMAGE}
          alt="MOSSERO fragrance editorial"
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-black/55" />
        <div className="relative h-full flex flex-col items-center justify-center text-center px-6">
          <p className="text-[11px] uppercase tracking-mega text-gold mb-8 fade-in visible">
            The Maison Mossero
          </p>
          <h1
            data-testid="hero-headline"
            className="font-serif font-light text-5xl sm:text-6xl lg:text-8xl text-offwhite leading-[1.05] max-w-5xl"
          >
            Power in every<br />
            <span className="italic">presence.</span>
          </h1>
          <div className="mt-10 mb-12">
            <span className="inline-block w-px h-12 bg-gold/70" />
          </div>
          <Link
            to="/fragrances"
            data-testid="hero-cta-discover"
            className="btn-outline-light"
          >
            Discover the Collection
          </Link>
        </div>
      </section>

      {/* SPLIT — OURA | VELOURA */}
      <section className="grid grid-cols-1 md:grid-cols-2" data-testid="split-section">
        {/* OURA */}
        <Link
          to="/fragrances/oura"
          data-testid="split-card-oura"
          className="product-card group relative bg-charcoal text-offwhite overflow-hidden"
        >
          <div className="aspect-[3/4] md:aspect-auto md:h-[820px] overflow-hidden relative">
            <img
              src={PRODUCTS.oura.image}
              alt="OURA"
              className="product-card-img w-full h-full object-cover opacity-90"
            />
            <div className="absolute inset-0 bg-gradient-to-b from-black/20 via-transparent to-charcoal/80" />
            <div className="absolute inset-x-0 bottom-0 p-10 lg:p-16">
              <p className="text-[11px] uppercase tracking-luxe text-gold mb-4">For Him</p>
              <h2 className="font-serif text-5xl lg:text-7xl mb-3 tracking-wider">OURA</h2>
              <p className="font-serif italic text-xl text-offwhite/80 mb-8">
                Power in every presence.
              </p>
              <span className="text-[11px] uppercase tracking-luxe text-gold link-underline">
                Shop Now
              </span>
            </div>
          </div>
        </Link>

        {/* VELOURA */}
        <Link
          to="/fragrances/veloura"
          data-testid="split-card-veloura"
          className="product-card group relative bg-offwhite text-ink overflow-hidden"
        >
          <div className="aspect-[3/4] md:aspect-auto md:h-[820px] overflow-hidden relative">
            <img
              src={PRODUCTS.veloura.image}
              alt="VELOURA"
              className="product-card-img w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-offwhite/85" />
            <div className="absolute inset-x-0 bottom-0 p-10 lg:p-16">
              <p className="text-[11px] uppercase tracking-luxe text-gold mb-4">For Her</p>
              <h2 className="font-serif text-5xl lg:text-7xl mb-3 tracking-wider text-ink">
                VELOURA
              </h2>
              <p className="font-serif italic text-xl text-ink/70 mb-8">
                A trace of the eternal feminine.
              </p>
              <span className="text-[11px] uppercase tracking-luxe text-gold link-underline">
                Shop Now
              </span>
            </div>
          </div>
        </Link>
      </section>

      {/* TEXT BANNER */}
      <FadeSection className="bg-cream py-32 lg:py-48 px-6 text-center">
        <p className="text-[11px] uppercase tracking-mega text-gold mb-10">
          Pronunciation
        </p>
        <h2 className="font-serif text-4xl sm:text-5xl lg:text-7xl text-ink leading-tight max-w-5xl mx-auto">
          Mo · <span className="italic text-gold">SEH</span> · ro.<br />
          <span className="text-3xl sm:text-4xl lg:text-5xl">
            From moss — quiet, enduring, alive.
          </span>
        </h2>
      </FadeSection>

      {/* STORY TEASER */}
      <FadeSection className="bg-offwhite">
        <div className="max-w-[1500px] mx-auto px-6 lg:px-12 py-24 lg:py-36 grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-24 items-center">
          <div className="aspect-[4/5] overflow-hidden">
            <img
              src={STORY_IMAGE}
              alt="The Mossero atelier"
              className="w-full h-full object-cover"
            />
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-luxe text-gold mb-6">
              The Maison
            </p>
            <h3 className="font-serif text-4xl lg:text-6xl text-ink leading-[1.1] mb-10">
              Born of stillness.<br />
              <span className="italic">Made to remain.</span>
            </h3>
            <hr className="gold-divider-short mb-10" />
            <p className="text-base text-ink/75 leading-[1.9] font-light max-w-lg mb-10">
              Mossero is a maison of two fragrances and one idea — that what
              endures is never loud. Each composition is built slowly, one accord
              at a time, around the patient grace of moss: living, ancient,
              unhurried.
            </p>
            <Link
              to="/our-story"
              data-testid="home-story-link"
              className="btn-outline-gold"
            >
              Read Our Story
            </Link>
          </div>
        </div>
      </FadeSection>

      {/* INSTAGRAM GRID */}
      <FadeSection className="bg-cream pt-24 pb-32 lg:pt-32 lg:pb-44">
        <div className="text-center mb-16">
          <p className="text-[11px] uppercase tracking-mega text-gold mb-6">
            Follow @mossero
          </p>
          <h3 className="font-serif text-3xl lg:text-5xl text-ink">
            The world, slowly.
          </h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-1">
          {INSTAGRAM_GRID.map((src, i) => (
            <div
              key={i}
              data-testid={`instagram-tile-${i}`}
              className="aspect-square overflow-hidden group"
            >
              <img
                src={src}
                alt={`editorial ${i + 1}`}
                className="w-full h-full object-cover transition-transform duration-1000 group-hover:scale-110"
              />
            </div>
          ))}
        </div>
      </FadeSection>
    </div>
  );
}
