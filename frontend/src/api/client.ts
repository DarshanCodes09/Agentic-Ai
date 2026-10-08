import axios, { AxiosError } from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" }
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("academic_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: unknown }>) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("academic_token");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.assign("/login");
      }
    }
    return Promise.reject(error);
  }
);

export function getApiErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return "Something went wrong. Please try again.";
  if (!error.response) return "Unable to reach the backend. Confirm the API server is running.";

  const detail = error.response.data?.detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "object" && item && "msg" in item) return String(item.msg);
        return String(item);
      })
      .join(" ");
  }
  if (typeof detail === "string") return detail;

  const statusMessages: Record<number, string> = {
    403: "You do not have access to this resource.",
    404: "The requested resource could not be found.",
    422: "Please check the submitted fields.",
    500: "The server hit an unexpected problem."
  };
  return statusMessages[error.response.status] ?? "Request failed. Please try again.";
}
