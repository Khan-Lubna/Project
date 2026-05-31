import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { ShoppingBag, Menu, X } from "lucide-react";
import { useCart } from "../context/CartContext";

const navLinks = [
  { to: "/", label: "Home" },
  { to: "/fragrances", label: "Fragrances" },
  { to: "/our-story", label: "Our Story" },
  { to: "/contact", label: "Contact" },
];

export default function Navigation() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { count } = useCart();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      data-testid="site-nav"
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled
          ? "bg-[#F5F0E8]/95 backdrop-blur-sm border-b border-[#C4A258]/30"
          : "bg-transparent"
      }`}
    >
      <div className="max-w-[1600px] mx-auto px-6 lg:px-12 py-5 lg:py-6 grid grid-cols-3 items-center">
        {/* Left links (desktop) */}
        <nav className="hidden lg:flex items-center gap-10">
          {navLinks.slice(0, 2).map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              data-testid={`nav-link-${l.label.toLowerCase().replace(/\s+/g, "-")}`}
              className={({ isActive }) =>
                `text-[11px] uppercase tracking-luxe text-ink hover:text-gold transition-colors duration-300 ${
                  isActive ? "text-gold" : ""
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </nav>

        {/* Mobile menu button */}
        <button
          data-testid="mobile-menu-toggle"
          onClick={() => setMobileOpen(!mobileOpen)}
          className="lg:hidden justify-self-start"
          aria-label="Menu"
        >
          {mobileOpen ? <X size={22} /> : <Menu size={22} />}
        </button>

        {/* Logo center */}
        <Link
          to="/"
          data-testid="nav-brand-logo"
          className="justify-self-center font-serif font-bold uppercase text-2xl lg:text-3xl tracking-[0.35em] text-black"
          style={{ color: "#000000" }}
        >
          MOSSERO
        </Link>

        {/* Right links + cart */}
        <div className="flex items-center gap-8 justify-self-end">
          <nav className="hidden lg:flex items-center gap-10">
            {navLinks.slice(2).map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                data-testid={`nav-link-${l.label.toLowerCase().replace(/\s+/g, "-")}`}
                className={({ isActive }) =>
                  `text-[11px] uppercase tracking-luxe text-ink hover:text-gold transition-colors duration-300 ${
                    isActive ? "text-gold" : ""
                  }`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
          <Link
            to="/cart"
            data-testid="nav-cart-icon"
            className="relative text-ink hover:text-gold transition-colors"
            aria-label="Cart"
          >
            <ShoppingBag size={20} strokeWidth={1.25} />
            {count > 0 && (
              <span
                data-testid="cart-count-badge"
                className="absolute -top-2 -right-3 text-[10px] font-medium text-black bg-gold w-4 h-4 flex items-center justify-center"
              >
                {count}
              </span>
            )}
          </Link>
        </div>
      </div>

      {/* Mobile menu overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden bg-cream border-t border-gold/30"
          data-testid="mobile-menu"
        >
          <nav className="flex flex-col items-center gap-6 py-10">
            {navLinks.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                onClick={() => setMobileOpen(false)}
                data-testid={`mobile-nav-link-${l.label.toLowerCase().replace(/\s+/g, "-")}`}
                className="text-sm uppercase tracking-luxe text-ink hover:text-gold"
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
}
