// Runtime API base.
// Uses REACT_APP_BACKEND_URL when provided, with the current site origin
// as a fallback for deployments where frontend and backend share the same origin.

function resolveBase() {
    return process.env.REACT_APP_BACKEND_URL || "";
}

export const API_BASE = resolveBase();
export const API = `${API_BASE}/api`;