import heroImage from "../assets/images/hero-image.png";
import ouraInstagram from "../assets/images/oura-instagram.png";
import velouraInstagram from "../assets/images/veloura-instagram.png";

// Static product data — mirrored on backend at /api/products
export const PRODUCTS = {
  oura: {
    slug: "oura",
    name: "OURA",
    type: "Eau de Parfum",
    size: "50ml",
    target: "For Him",
    tagline: "Power in every presence.",
    price: 999.0,
    currency: "INR",
    theme: "dark",
    description:
      "OURA is a study in restraint and command. A masculine composition that opens with the bright cut of bergamot and the spark of fresh pepper, softens through a quiet heart of lavender, geranium and a whispered spice, and settles into the long, low warmth of ambroxan, cedarwood and musk. It is presence — felt before it is named.",
    notes: {
      top: ["Bergamot", "Fresh Pepper"],
      heart: ["Lavender", "Geranium", "Spicy Accord"],
      base: ["Ambroxan", "Cedarwood", "Warm Musk"],
    },
    image: ouraInstagram,
    secondary:
      "https://images.unsplash.com/photo-1709662217788-6a8a1b31562a?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600",
  },
  veloura: {
    slug: "veloura",
    name: "VELOURA",
    type: "Eau de Parfum",
    size: "50ml",
    target: "For Her",
    tagline: "A trace of the eternal feminine.",
    price: 999.0,
    currency: "INR",
    theme: "light",
    description:
      "VELOURA is luminous and unhurried. A feminine bouquet built on the soft, narcotic light of jasmine, the velvet weight of tuberose and the rare, honeyed bloom of Rangoon creeper. Romantic without nostalgia. Quiet, enduring, alive.",
    notes: {
      top: ["Jasmine"],
      heart: ["Tuberose"],
      base: ["Rangoon Creeper"],
    },
    image: velouraInstagram,
    secondary:
      "https://images.unsplash.com/photo-1760113559708-84e7a148ec68?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600",
  },
};

export const HERO_IMAGE = heroImage;

export const STORY_IMAGE =
  "https://images.unsplash.com/photo-1709662217788-6a8a1b31562a?crop=entropy&cs=srgb&fm=jpg&q=85&w=1800";

export const INSTAGRAM_GRID = [
  ouraInstagram,
  "https://images.unsplash.com/photo-1617733401065-c7bdf0b33417?crop=entropy&cs=srgb&fm=jpg&q=85&w=900",
  "https://images.unsplash.com/photo-1676577419866-92359c44c983?crop=entropy&cs=srgb&fm=jpg&q=85&w=900",
  "https://images.unsplash.com/photo-1612303544167-5871c2331e36?crop=entropy&cs=srgb&fm=jpg&q=85&w=900",
  "https://images.unsplash.com/photo-1612301988752-5a5b19021f45?crop=entropy&cs=srgb&fm=jpg&q=85&w=900",
  velouraInstagram,
];
