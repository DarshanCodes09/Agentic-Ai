import { apiClient } from "./client";
import type { LoginRequest, RegisterRequest, TokenResponse, UserBrief } from "../types/api";

export async function login(payload: LoginRequest) {
  const { data } = await apiClient.post<TokenResponse>("/auth/login", payload);
  return data;
}

export async function register(payload: RegisterRequest) {
  const { data } = await apiClient.post<UserBrief & { message: string }>("/auth/register", payload);
  return data;
}

export async function getCurrentUser() {
  const { data } = await apiClient.get<UserBrief>("/auth/me");
  return data;
}
