import { Link } from "react-router-dom";
import FadeSection from "../components/FadeSection";
import { STORY_IMAGE, INSTAGRAM_GRID } from "../lib/products";

export default function OurStory() {
  return (
    <div data-testid="our-story-page" className="bg-cream">
      {/* OPENER */}
      <section className="relative h-[85vh] min-h-[680px] w-full overflow-hidden pt-24">
        <img
          src={STORY_IMAGE}
          alt="Mossero atelier"
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-black/45" />
        <div className="relative h-full flex flex-col items-center justify-center text-center px-6">
          <p className="text-[11px] uppercase tracking-mega text-gold mb-8">
            The Maison Mossero
          </p>
          <h1 className="font-serif text-5xl sm:text-6xl lg:text-8xl text-offwhite leading-tight max-w-5xl">
            A trace of <span className="italic">elegance.</span>
          </h1>
        </div>
      </section>

      {/* INTRO COPY */}
      <FadeSection className="max-w-3xl mx-auto px-6 py-28 lg:py-40 text-center">
        <p className="text-[11px] uppercase tracking-mega text-gold mb-10">
          Founding Principle
        </p>
        <h2 className="font-serif text-3xl lg:text-5xl text-ink leading-snug mb-14">
          Mossero is built around a single<br />
          <span className="italic">unhurried idea.</span>
        </h2>
        <hr className="gold-divider-short mb-14" />
        <div className="space-y-8 text-base lg:text-lg text-ink/75 font-light leading-[2]">
          <p>
            What endures is never loud. It is quiet, considered, and patient.
            From a small atelier, two fragrances were composed slowly — one
            accord at a time, one season at a time — until each one felt like
            something already known, already remembered.
          </p>
          <p>
            We named the maison after the moss that returned to the studio
            walls each spring: green, low, alive without effort. A reminder
            that elegance does not announce itself. It simply remains.
          </p>
        </div>
      </FadeSection>

      {/* PULL QUOTE */}
      <FadeSection className="bg-charcoal text-offwhite">
        <div className="max-w-5xl mx-auto px-6 py-32 lg:py-48 text-center">
          <p className="text-[11px] uppercase tracking-mega text-gold mb-12">
            Pronunciation
          </p>
          <blockquote className="font-serif italic text-4xl sm:text-5xl lg:text-7xl text-gold leading-tight">
            "Mo-SEH-ro.<br />
            From moss — quiet, enduring, alive."
          </blockquote>
        </div>
      </FadeSection>

      {/* TWO-COLUMN STORY */}
      <FadeSection className="max-w-[1400px] mx-auto px-6 lg:px-12 py-28 lg:py-40 grid grid-cols-1 lg:grid-cols-2 gap-16 lg:gap-24 items-center">
        <div>
          <p className="text-[11px] uppercase tracking-luxe text-gold mb-6">
            The Compositions
          </p>
          <h3 className="font-serif text-4xl lg:text-6xl text-ink leading-[1.1] mb-10">
            Two fragrances,<br />
            <span className="italic">one signature.</span>
          </h3>
          <hr className="gold-divider-short mb-10" />
          <p className="text-base text-ink/75 leading-[1.9] font-light max-w-xl mb-10">
            <span className="font-medium text-ink">OURA</span> — for him —
            opens with bergamot and the bright cut of pepper, and resolves into
            ambroxan, cedarwood and a long, low warmth. Power held in restraint.
          </p>
          <p className="text-base text-ink/75 leading-[1.9] font-light max-w-xl mb-12">
            <span className="font-medium text-ink">VELOURA</span> — for her —
            is luminous and unhurried: jasmine and tuberose softened by the
            rare bloom of Rangoon creeper. Romantic without nostalgia.
          </p>
          <Link
            to="/fragrances"
            data-testid="story-explore-collection"
            className="btn-outline-gold"
          >
            Explore the Collection
          </Link>
        </div>
        <div className="aspect-[4/5] overflow-hidden">
          <img
            src={INSTAGRAM_GRID[3]}
            alt="Maison Mossero"
            className="w-full h-full object-cover"
          />
        </div>
      </FadeSection>
    </div>
  );
}
