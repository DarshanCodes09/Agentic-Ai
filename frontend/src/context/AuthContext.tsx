import { createContext, useContext, useEffect, useMemo, useState } from "react";
import * as authApi from "../api/auth";
import type { LoginRequest, RegisterRequest, TokenResponse, UserBrief, UserRole } from "../types/api";

interface AuthContextValue {
  user: UserBrief | null;
  token: string | null;
  role: UserRole | null;
  loading: boolean;
  login: (payload: LoginRequest) => Promise<TokenResponse>;
  register: (payload: RegisterRequest) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserBrief | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("academic_token"));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function hydrate() {
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const current = await authApi.getCurrentUser();
        if (active) setUser(current);
      } catch {
        localStorage.removeItem("academic_token");
        if (active) {
          setToken(null);
          setUser(null);
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    hydrate();
    return () => {
      active = false;
    };
  }, [token]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      role: user?.role ?? null,
      loading,
      login: async (payload) => {
        const response = await authApi.login(payload);
        localStorage.setItem("academic_token", response.access_token);
        setToken(response.access_token);
        setUser({
          id: response.user_id,
          full_name: response.full_name,
          email: response.email,
          role: response.role,
          is_active: true
        });
        return response;
      },
      register: async (payload) => {
        await authApi.register(payload);
      },
      logout: () => {
        localStorage.removeItem("academic_token");
        setToken(null);
        setUser(null);
      }
    }),
    [loading, token, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
