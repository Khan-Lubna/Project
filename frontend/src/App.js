import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";

import Layout from "@/components/Layout";
import { CartProvider } from "@/context/CartContext";
import Home from "@/pages/Home";
import Fragrances from "@/pages/Fragrances";
import Product from "@/pages/Product";
import OurStory from "@/pages/OurStory";
import Contact from "@/pages/Contact";
import Cart from "@/pages/Cart";
import CheckoutSuccess from "@/pages/CheckoutSuccess";
import OrderTracking from "@/pages/OrderTracking";
import QRCheckout from "@/pages/QRCheckout";
import QRPayment from "@/pages/QRPayment";

export default function App() {
  return (
    <CartProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/fragrances" element={<Fragrances />} />
            <Route path="/fragrances/:slug" element={<Product />} />
            <Route path="/our-story" element={<OurStory />} />
            <Route path="/contact" element={<Contact />} />
            <Route path="/cart" element={<Cart />} />
            <Route path="/cart/success" element={<CheckoutSuccess />} />
            <Route path="/track" element={<OrderTracking />} />
            <Route path="/qr-checkout" element={<QRCheckout />} />
            <Route path="/qr-pay" element={<QRPayment />} />
            <Route path="*" element={<Home />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster
        position="top-center"
        toastOptions={{
          style: {
            background: "#1A1A1A",
            color: "#F5F0E8",
            border: "1px solid #C4A258",
            borderRadius: 0,
            fontFamily: "Montserrat, sans-serif",
            letterSpacing: "0.05em",
          },
        }}
      />
    </CartProvider>
  );
}
