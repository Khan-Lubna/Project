// Lazy-load Razorpay Checkout script
let razorpayLoadingPromise = null;

export function loadRazorpay() {
  if (typeof window !== "undefined" && window.Razorpay) {
    return Promise.resolve(window.Razorpay);
  }
  if (razorpayLoadingPromise) return razorpayLoadingPromise;

  razorpayLoadingPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => resolve(window.Razorpay);
    script.onerror = () => {
      razorpayLoadingPromise = null;
      reject(new Error("Failed to load Razorpay checkout"));
    };
    document.body.appendChild(script);
  });

  return razorpayLoadingPromise;
}
