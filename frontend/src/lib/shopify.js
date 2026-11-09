// Shopify Storefront API connector (Phase 1).
// This module is intentionally NOT wired into the live storefront yet.
// It defaults to disabled via REACT_APP_USE_SHOPIFY_CATALOG (defaults to false).

import { PRODUCTS as STATIC_PRODUCTS } from "./products";

const STORE_DOMAIN = process.env.REACT_APP_SHOPIFY_STORE_DOMAIN || "";
const API_VERSION = process.env.REACT_APP_SHOPIFY_STOREFRONT_API_VERSION || "2026-10";
const STOREFRONT_TOKEN = process.env.REACT_APP_SHOPIFY_STOREFRONT_TOKEN || "";

export const USE_SHOPIFY_CATALOG =
  process.env.REACT_APP_USE_SHOPIFY_CATALOG === "true";

const PRODUCTS_QUERY = `
  query Products($first: Int!) {
    products(first: $first) {
      edges {
        node {
          id
          handle
          title
          description
          featuredImage { url altText }
          priceRange { minVariantPrice { amount currencyCode } }
          variants(first: 50) {
            edges {
              node {
                id
                title
                availableForSale
                price { amount currencyCode }
                selectedOptions { name value }
              }
            }
          }
        }
      }
    }
  }
`;

const PRODUCT_BY_HANDLE_QUERY = `
  query ProductByHandle($handle: String!) {
    product(handle: $handle) {
      id
      handle
      title
      description
      featuredImage { url altText }
      priceRange { minVariantPrice { amount currencyCode } }
      variants(first: 50) {
        edges {
          node {
            id
            title
            availableForSale
            price { amount currencyCode }
            selectedOptions { name value }
          }
        }
      }
    }
  }
`;

function assertConfigured() {
  if (!STORE_DOMAIN || !STOREFRONT_TOKEN) {
    throw new Error(
      "Shopify Storefront API is not configured. Set REACT_APP_SHOPIFY_STORE_DOMAIN and REACT_APP_SHOPIFY_STOREFRONT_TOKEN."
    );
  }
}

async function storefrontRequest(query, variables) {
  assertConfigured();

  let response;
  try {
    response = await fetch(
      `https://${STORE_DOMAIN}/api/${API_VERSION}/graphql.json`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Shopify-Storefront-Access-Token": STOREFRONT_TOKEN,
        },
        body: JSON.stringify({ query, variables }),
      }
    );
  } catch (err) {
    throw new Error(`Shopify network error: ${err && err.message ? err.message : "request failed"}`);
  }

  if (!response.ok) {
    throw new Error(`Shopify HTTP error: ${response.status} ${response.statusText}`);
  }

  let json;
  try {
    json = await response.json();
  } catch (err) {
    throw new Error("Shopify response was not valid JSON.");
  }

  if (json && Array.isArray(json.errors) && json.errors.length) {
    const messages = json.errors.map((e) => (e && e.message) || "Unknown error").join("; ");
    throw new Error(`Shopify GraphQL error: ${messages}`);
  }

  return json && json.data ? json.data : {};
}

function toNumber(value) {
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : 0;
}

function staticFallback(handle) {
  return STATIC_PRODUCTS && STATIC_PRODUCTS[handle] ? STATIC_PRODUCTS[handle] : null;
}

function getShopifyHandle(slug) {
  const handles = {
    oura: "aura",
    veloura: "veloura",
  };

  return handles[slug] || slug;
}

function getStaticProduct(handle) {
  const staticSlug = {
    aura: "oura",
    veloura: "veloura",
  }[handle] || handle;

  return staticFallback(staticSlug);
}

function mapVariant(variant) {
  if (!variant) return null;
  const sizeOption = (variant.selectedOptions || []).find(
    (opt) => (opt.name || "").toLowerCase() === "size"
  );
  return {
    id: variant.id,
    title: variant.title,
    price: toNumber(variant.price && variant.price.amount),
    currency: (variant.price && variant.price.currencyCode) || "",
    availableForSale: Boolean(variant.availableForSale),
    selectedOptions: variant.selectedOptions || [],
    size: sizeOption ? sizeOption.value : (variant.title || ""),
  };
}

// function mapProduct(node) {
//   if (!node) return null;
//   const handle = node.handle;
//   const fallback = staticFallback(handle);

//   const variants = (node.variants && node.variants.edges
//     ? node.variants.edges.map((e) => mapVariant(e.node)).filter(Boolean)
//     : []);

//   const primaryVariant = variants.length ? variants[0] : null;
//   const minPrice = node.priceRange && node.priceRange.minVariantPrice
//     ? node.priceRange.minVariantPrice
//     : (primaryVariant ? { amount: String(primaryVariant.price), currencyCode: primaryVariant.currency } : null);

//   const sizeFromVariant = primaryVariant ? primaryVariant.size : "";

//   return {
//     slug: handle,
//     name: node.title || (fallback ? fallback.name : ""),
//     type: fallback ? fallback.type : "",
//     size: fallback ? fallback.size : (sizeFromVariant || ""),
//     target: fallback ? fallback.target : "",
//     tagline: fallback ? fallback.tagline : "",
//     price: minPrice ? toNumber(minPrice.amount) : (fallback ? fallback.price : 0),
//     currency: minPrice ? minPrice.currencyCode : (fallback ? fallback.currency : ""),
//     theme: fallback ? fallback.theme : "light",
//     description: node.description || (fallback ? fallback.description : ""),
//     notes: fallback ? fallback.notes : { top: [], heart: [], base: [] },
//     image: (node.featuredImage && node.featuredImage.url) || (fallback ? fallback.image : ""),
//     secondary: fallback ? fallback.secondary : ((node.featuredImage && node.featuredImage.url) || ""),
//     shopify: {
//       productId: node.id,
//       variants,
//     },
//   };
// }

function mapProduct(node) {
  if (!node || !node.handle) return null;

  const fallback = getStaticProduct(node.handle);

  if (!fallback) return null;

  const variants = (
    node.variants?.edges || []
  )
    .map((edge) => mapVariant(edge.node))
    .filter(Boolean);

  const selectedVariant =
    variants.find((variant) => variant.availableForSale) ||
    variants[0] ||
    null;

  // Use the same variant that the cart will select.
  const shopifyPrice = selectedVariant?.price;
  const shopifyCurrency = selectedVariant?.currency;

  return {
    ...fallback,

    ...(selectedVariant
      ? {
          price: shopifyPrice,
          currency: shopifyCurrency,
        }
      : {}),

    shopify: {
      productId: node.id,
      handle: node.handle,
      variants,
    },
  };
}

// export async function fetchProducts(first = 50) {
//   const data = await storefrontRequest(PRODUCTS_QUERY, { first });
//   const edges = (data.products && data.products.edges) || [];
//   return edges.map((edge) => mapProduct(edge.node)).filter(Boolean);
// }

export async function fetchProducts() {
  const data = await storefrontRequest(PRODUCTS_QUERY, {
    first: 50,
  });

  const edges = (data.products && data.products.edges) || [];

  return edges
    .map((edge) => mapProduct(edge.node))
    .filter(Boolean);
}

// export async function fetchProductByHandle(handle) {
//   if (!handle) return null;
//   const data = await storefrontRequest(PRODUCT_BY_HANDLE_QUERY, { handle });
//   return mapProduct(data.product);
// }

export async function fetchProductByHandle(handle) {
  if (!handle) return null;

  const shopifyHandle = getShopifyHandle(handle);

  const data = await storefrontRequest(
    PRODUCT_BY_HANDLE_QUERY,
    { handle: shopifyHandle }
  );

  return mapProduct(data.product);
}

export default {
  USE_SHOPIFY_CATALOG,
  fetchProducts,
  fetchProductByHandle,
};
