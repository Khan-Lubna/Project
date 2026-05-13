import { Link } from "react-router-dom";
import { Instagram, Twitter, Facebook } from "lucide-react";

export default function Footer() {
  return (
    <footer
      data-testid="site-footer"
      className="bg-cream border-t border-gold/40"
    >
      <div className="max-w-[1600px] mx-auto px-6 lg:px-12 py-20 lg:py-28">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-12 lg:gap-16">
          <div className="lg:col-span-2">
            <h2
              className="font-serif font-bold uppercase text-3xl lg:text-4xl tracking-[0.35em] text-black mb-6"
              style={{ color: "#000000" }}
            >
              MOSSERO
            </h2>
            <p className="text-sm text-ink/70 max-w-md leading-relaxed font-light">
              Leave a trace of elegance wherever you go.
            </p>
          </div>

          <div>
            <h4 className="text-[11px] uppercase tracking-luxe text-ink mb-6 font-medium">
              Maison
            </h4>
            <ul className="space-y-3">
              <li>
                <Link
                  to="/our-story"
                  data-testid="footer-link-our-story"
                  className="text-sm text-ink/75 hover:text-gold transition-colors font-light"
                >
                  Our Story
                </Link>
              </li>
              <li>
                <Link
                  to="/fragrances"
                  data-testid="footer-link-fragrances"
                  className="text-sm text-ink/75 hover:text-gold transition-colors font-light"
                >
                  Fragrances
                </Link>
              </li>
              <li>
                <Link
                  to="/track"
                  data-testid="footer-link-track"
                  className="text-sm text-ink/75 hover:text-gold transition-colors font-light"
                >
                  Track Order
                </Link>
              </li>
              <li>
                <Link
                  to="/contact"
                  data-testid="footer-link-contact"
                  className="text-sm text-ink/75 hover:text-gold transition-colors font-light"
                >
                  Contact
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-[11px] uppercase tracking-luxe text-ink mb-6 font-medium">
              Connect
            </h4>
            <div className="flex items-center gap-5">
              <a
                href="https://instagram.com"
                target="_blank"
                rel="noreferrer"
                data-testid="footer-instagram"
                aria-label="Instagram"
                className="text-gold hover:text-ink transition-colors"
              >
                <Instagram size={18} strokeWidth={1.25} />
              </a>
              <a
                href="https://twitter.com"
                target="_blank"
                rel="noreferrer"
                data-testid="footer-twitter"
                aria-label="Twitter"
                className="text-gold hover:text-ink transition-colors"
              >
                <Twitter size={18} strokeWidth={1.25} />
              </a>
              <a
                href="https://facebook.com"
                target="_blank"
                rel="noreferrer"
                data-testid="footer-facebook"
                aria-label="Facebook"
                className="text-gold hover:text-ink transition-colors"
              >
                <Facebook size={18} strokeWidth={1.25} />
              </a>
            </div>
          </div>
        </div>

        <hr className="gold-divider mt-20 mb-8" />
        <p className="text-[11px] uppercase tracking-luxe text-ink/60 text-center">
          © 2026 Mossero — All rights reserved
        </p>
      </div>
    </footer>
  );
}
