import { Outlet, useLocation } from "react-router-dom";
import { useEffect } from "react";
import Navigation from "./Navigation";
import Footer from "./Footer";

export default function Layout() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [pathname]);

  return (
    <div className="min-h-screen bg-cream text-ink flex flex-col">
      <Navigation />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
