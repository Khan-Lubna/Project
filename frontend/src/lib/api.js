// Runtime API base — resolves to the current site's origin so the same build
// works in both preview (moss-refined.preview.emergentagent.com) and
// production (mossero.in). Falls back to REACT_APP_BACKEND_URL for SSR / tests.

function resolveBase() {
  if (typeof window !== "undefined" && window.location && window.location.origin) {
    return window.location.origin;
  }
  return process.env.REACT_APP_BACKEND_URL || "";
}

export const API_BASE = resolveBase();
export const API = `${API_BASE}/api`;
