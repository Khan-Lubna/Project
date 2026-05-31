// Currency formatting — single source of truth.
const SYMBOLS = { INR: "₹", USD: "$", EUR: "€", GBP: "£" };

export function formatPrice(amount, currency = "INR") {
    const sym = SYMBOLS[(currency || "INR").toUpperCase()] || "";
    const n = Number(amount || 0);
    return `${sym}${n.toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    })}`;
}
