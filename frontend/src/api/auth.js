import apiClient from "./client";

export async function signup({ email, password, name }) {
  const { data } = await apiClient.post("/auth/signup", { email, password, name });
  return data;
}

export async function login({ email, password }) {
  const { data } = await apiClient.post("/auth/login", { email, password });
  return data;
}

export async function getCurrentUser() {
  const { data } = await apiClient.get("/users/me");
  return data;
}

export function storeTokens({ access_token, refresh_token }) {
  localStorage.setItem("aria_access_token", access_token);
  localStorage.setItem("aria_refresh_token", refresh_token);
}

export function clearTokens() {
  localStorage.removeItem("aria_access_token");
  localStorage.removeItem("aria_refresh_token");
}
