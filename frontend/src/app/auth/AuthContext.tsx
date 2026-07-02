import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { clearAuthToken, getCurrentUser, loginUser, logoutUser, setAuthToken } from "../api/client";
import type { AuthSession, LoginPayload, UserPublic } from "../api/types";
import { clearStoredAuthToken, getStoredAuthToken, storeAuthToken } from "./storage";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  user: UserPublic | null;
  token: string | null;
  status: AuthStatus;
  isAuthenticated: boolean;
  login: (payload: LoginPayload) => Promise<AuthSession>;
  logout: () => Promise<void>;
  refreshCurrentUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
* Proporciona token de sesion, usuario autenticado y acciones de entrada y salida.
* Al arrancar intenta recuperar el token almacenado, valida la sesion contra el
* backend y sincroniza el cliente API con la cabecera Authorization.
*/
export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [token, setTokenState] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return getStoredAuthToken();
  });
  const [user, setUser] = useState<UserPublic | null>(null);

  useEffect(() => {
    if (!token) {
      clearAuthToken();
      setUser(null);
      setStatus("anonymous");
      return;
    }
    let cancelled = false;
    setAuthToken(token);
    setStatus("loading");
    void getCurrentUser()
      .then((currentUser) => {
        if (cancelled) return;
        setUser(currentUser);
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        clearStoredAuthToken();
        clearAuthToken();
        setTokenState(null);
        setUser(null);
        setStatus("anonymous");
      });
    return () => { cancelled = true; };
  }, [token]);

  const value = useMemo<AuthContextValue>(() => ({
    user, token, status,
    isAuthenticated: status === "authenticated" && Boolean(user) && Boolean(token),
    async login(payload: LoginPayload) {
      const session = await loginUser(payload);
      storeAuthToken(session.access_token);
      setAuthToken(session.access_token);
      setTokenState(session.access_token);
      setUser(session.user);
      setStatus("authenticated");
      return session;
    },
    async logout() {
      try { await logoutUser(); } catch {}
      finally {
        clearStoredAuthToken();
        clearAuthToken();
        setTokenState(null);
        setUser(null);
        setStatus("anonymous");
      }
    },
    async refreshCurrentUser() {
      if (!token) { setUser(null); setStatus("anonymous"); return; }
      const currentUser = await getCurrentUser();
      setUser(currentUser);
      setStatus("authenticated");
    },
  }), [status, token, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Devuelve el contexto de autenticacion actual y exige el uso dentro del proveedor. */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth debe usarse dentro de AuthProvider.");
  return context;
}
