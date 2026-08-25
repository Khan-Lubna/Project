// Runtime API base.
// Uses REACT_APP_BACKEND_URL when provided, with the current site origin
// as a fallback for deployments where frontend and backend share the same origin.

function resolveBase() {
    if (process.env.REACT_APP_BACKEND_URL) {
        return process.env.REACT_APP_BACKEND_URL;
    }

    if (
        typeof window !== "undefined" &&
        window.location &&
        window.location.origin
    ) {
        return window.location.origin;
    }

    return "";
}

export const API_BASE = resolveBase();
export const API = `${API_BASE}/api`;