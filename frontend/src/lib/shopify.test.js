import { PRODUCTS as STATIC_PRODUCTS } from "./products";

function baseEnv(overrides = {}) {
  return {
    REACT_APP_SHOPIFY_STORE_DOMAIN: "example.myshopify.com",
    REACT_APP_SHOPIFY_STOREFRONT_API_VERSION: "2026-10",
    REACT_APP_SHOPIFY_STOREFRONT_TOKEN: "test-token",
    REACT_APP_USE_SHOPIFY_CATALOG: "false",
    ...overrides,
  };
}

function setEnv(env) {
  Object.keys(env).forEach((k) => {
    process.env[k] = env[k];
  });
}

function clearEnv(keys) {
  keys.forEach((k) => delete process.env[k]);
}

const SHOPIFY_KEYS = [
  "REACT_APP_SHOPIFY_STORE_DOMAIN",
  "REACT_APP_SHOPIFY_STOREFRONT_API_VERSION",
  "REACT_APP_SHOPIFY_STOREFRONT_TOKEN",
  "REACT_APP_USE_SHOPIFY_CATALOG",
];

beforeEach(() => {
  jest.resetModules();
  clearEnv(SHOPIFY_KEYS);
  global.fetch = jest.fn();
});

afterEach(() => {
  jest.restoreAllMocks();
  clearEnv(SHOPIFY_KEYS);
});

describe("feature flag", () => {
  test("disabled unless explicitly true", async () => {
    setEnv(baseEnv({ REACT_APP_USE_SHOPIFY_CATALOG: "false" }));
    const mod = await import("./shopify");
    expect(mod.USE_SHOPIFY_CATALOG).toBe(false);

    jest.resetModules();
    clearEnv(SHOPIFY_KEYS);
    setEnv(baseEnv({ REACT_APP_USE_SHOPIFY_CATALOG: "true" }));
    const mod2 = await import("./shopify");
    expect(mod2.USE_SHOPIFY_CATALOG).toBe(true);

    jest.resetModules();
    clearEnv(SHOPIFY_KEYS);
    setEnv(baseEnv());
    delete process.env.REACT_APP_USE_SHOPIFY_CATALOG;
    const mod3 = await import("./shopify");
    expect(mod3.USE_SHOPIFY_CATALOG).toBe(false);
  });
});

test("ignores Shopify products not present in static catalog", async () => {
  setEnv(baseEnv());

  const { fetchProducts } = await import("./shopify");

  const node = {
    id: "gid://shopify/Product/2",
    handle: "new-scent",
    title: "NEW",
    variants: { edges: [] },
  };

  global.fetch.mockResolvedValue({
    ok: true,
    status: 200,
    statusText: "OK",
    json: async () => ({
      data: {
        products: {
          edges: [{ node }],
        },
      },
    }),
  });

  const products = await fetchProducts();

  expect(products).toHaveLength(0);
});

test("throws when token missing", async () => {
  setEnv(baseEnv({ REACT_APP_SHOPIFY_STOREFRONT_TOKEN: "" }));
  const { fetchProducts } = await import("./shopify");
  await expect(fetchProducts()).rejects.toThrow(/not configured/i);
  expect(global.fetch).not.toHaveBeenCalled();
});

describe("network and HTTP errors", () => {
  test("network failure", async () => {
    setEnv(baseEnv());
    const { fetchProducts } = await import("./shopify");
    global.fetch.mockRejectedValue(new Error("boom"));
    await expect(fetchProducts()).rejects.toThrow(/network error/i);
  });

  test("HTTP error", async () => {
    setEnv(baseEnv());
    const { fetchProducts } = await import("./shopify");
    global.fetch.mockResolvedValue({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      json: async () => ({}),
    });
    await expect(fetchProducts()).rejects.toThrow(/HTTP error: 401/);
  });

  test("invalid JSON", async () => {
    setEnv(baseEnv());
    const { fetchProducts } = await import("./shopify");
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => {
        throw new Error("bad json");
      },
    });
    await expect(fetchProducts()).rejects.toThrow(/not valid JSON/i);
  });

  test("GraphQL errors", async () => {
    setEnv(baseEnv());
    const { fetchProducts } = await import("./shopify");
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({ errors: [{ message: "boom" }] }),
    });
    await expect(fetchProducts()).rejects.toThrow(/GraphQL error: boom/);
  });
});

describe("product mapping", () => {
  const shopifyProduct = {
    id: "gid://shopify/Product/1",
    handle: "oura",
    title: "OURA",
    description: "desc",
    featuredImage: { url: "https://img/oura.jpg", altText: "oura" },
    priceRange: { minVariantPrice: { amount: "1000.00", currencyCode: "INR" } },
    variants: {
      edges: [
        {
          node: {
            id: "gid://shopify/ProductVariant/10",
            title: "Default Title",
            availableForSale: true,
            price: { amount: "1000.00", currencyCode: "INR" },
            selectedOptions: [{ name: "Size", value: "50ml" }],
          },
        },
      ],
    },
  };

  test("keeps static product data and maps Shopify variant data", async () => {
    setEnv(baseEnv());

    const { fetchProducts } = await import("./shopify");

    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({
        data: {
          products: {
            edges: [{ node: shopifyProduct }],
          },
        },
      }),
    });

    const products = await fetchProducts();

    expect(products).toHaveLength(1);

    const product = products[0];
    const staticProduct = STATIC_PRODUCTS.oura;

    // Static catalog remains the presentation source.
    expect(product.name).toBe(staticProduct.name);
    // expect(product.price).toBe(staticProduct.price);
    expect(product.price).toBe(1000);
    // expect(product.currency).toBe(staticProduct.currency);
    expect(product.currency).toBe("INR");
    expect(product.shopify.variants[0].price).toBe(1000);
    expect(product.image).toBe(staticProduct.image);
    expect(product.type).toBe(staticProduct.type);
    expect(product.notes).toEqual(staticProduct.notes);

    // Shopify supplies product and variant information.
    expect(product.shopify.productId).toBe("gid://shopify/Product/1");
    expect(product.shopify.variants[0].id).toBe(
      "gid://shopify/ProductVariant/10"
    );
    expect(product.shopify.variants[0].price).toBe(1000);
    expect(product.shopify.variants[0].availableForSale).toBe(true);
  });

  test("keeps static image even when Shopify provides an image", async () => {
    setEnv(baseEnv());

    const { fetchProducts } = await import("./shopify");

    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({
        data: {
          products: {
            edges: [{ node: shopifyProduct }],
          },
        },
      }),
    });

    const products = await fetchProducts();

    expect(products[0].image).toBe(STATIC_PRODUCTS.oura.image);
  });

  test("fetchProductByHandle maps single product", async () => {
    setEnv(baseEnv());
    const { fetchProductByHandle } = await import("./shopify");
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({ data: { product: shopifyProduct } }),
    });
    const p = await fetchProductByHandle("oura");
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/graphql.json"),
      expect.objectContaining({
        body: expect.stringContaining('"handle":"aura"'),
      })
    );
    expect(p.slug).toBe("oura");
    expect(p.shopify.productId).toBe("gid://shopify/Product/1");
  });

  test("fetchProductByHandle returns null for missing", async () => {
    setEnv(baseEnv());
    const { fetchProductByHandle } = await import("./shopify");
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({ data: { product: null } }),
    });
    const p = await fetchProductByHandle("nope");
    expect(p).toBeNull();
  });
});
