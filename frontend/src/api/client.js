import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("aria_access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Access tokens expire after an hour. Without this, a candidate who leaves the
// tab open gets a bare "could not load" on their next action and loses the
// session they were part-way through.
let refreshInFlight = null;

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem("aria_refresh_token");
  if (!refreshToken) throw new Error("No refresh token");

  // Bare axios, not apiClient — this must not recurse through the interceptor.
  const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
    refresh_token: refreshToken,
  });
  localStorage.setItem("aria_access_token", data.access_token);
  localStorage.setItem("aria_refresh_token", data.refresh_token);
  return data.access_token;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const isAuthCall = original?.url?.includes("/auth/");

    if (error.response?.status !== 401 || original?._retried || isAuthCall) {
      return Promise.reject(error);
    }

    original._retried = true;
    try {
      // Share one refresh across concurrent 401s rather than firing several.
      refreshInFlight = refreshInFlight ?? refreshAccessToken();
      const token = await refreshInFlight;
      original.headers.Authorization = `Bearer ${token}`;
      return apiClient(original);
    } catch (refreshError) {
      localStorage.removeItem("aria_access_token");
      localStorage.removeItem("aria_refresh_token");
      return Promise.reject(refreshError);
    } finally {
      refreshInFlight = null;
    }
  }
);

export default apiClient;
