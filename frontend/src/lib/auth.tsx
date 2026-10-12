/**
 * Session/user/permission state - mirrors the Reflex app's AuthState (itself a
 * port of the original lib/auth.tsx).
 *
 * Tokens persist in localStorage under the same keys the previous frontends
 * used (axon.accessToken / axon.refreshToken), so a reload doesn't sign the
 * user out; the user object is re-fetched via /auth/me on load rather than
 * persisted. Refresh-token rotation is guarded by a single in-flight promise:
 * the backend treats reuse of an already-rotated refresh token as theft and
 * revokes every session for the user, so several concurrent 401s must share
 * ONE refresh instead of each replaying the stale token.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ApiError, getBlob, request, type RequestOptions } from "@/lib/api";
import { permits } from "@/lib/nav";

const ACCESS_KEY = "axon.accessToken";
const REFRESH_KEY = "axon.refreshToken";
/** Refresh well under the access-token TTL so a role edited elsewhere takes effect within minutes. */
const PROACTIVE_REFRESH_MS = 5 * 60 * 1000;

export interface Role {
  id?: string;
  name: string;
}

export interface User {
  id: string;
  email: string;
  displayName: string;
  roles: Role[];
  permissions: string[];
  warehouseIds: string[] | null;
  factoryIds: string[] | null;
  mfaEnabled?: boolean;
  [k: string]: unknown;
}

export type AuthStatus = "loading" | "authenticated" | "anonymous";

export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  user: User;
}

interface LoginInput {
  email: string;
  password: string;
  mfaCode?: string;
  mfaRecoveryCode?: string;
}

interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  permissions: string[];
  /** "*" grants everything; "resource:*" every action on a resource. */
  can: (permission: string) => boolean;
  canAny: (permissions: string[]) => boolean;
  /** Returns nothing on success; resolves with { mfaRequired: true } when a second factor is needed. */
  login: (input: LoginInput) => Promise<{ mfaRequired: boolean }>;
  setSession: (resp: LoginResponse) => void;
  logout: () => Promise<void>;
  /** Authorised JSON request: attaches the token, refreshes once on 401 and retries. */
  api: <T = unknown>(method: string, path: string, opts?: Omit<RequestOptions, "token">) => Promise<T>;
  apiBlob: (path: string, opts?: Omit<RequestOptions, "token">) => ReturnType<typeof getBlob>;
  reloadUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readToken(key: string): string {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function writeToken(key: string, value: string) {
  try {
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch {
    /* storage blocked - the session just won't survive a reload */
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<User | null>(null);
  const refreshing = useRef<Promise<boolean> | null>(null);
  const hydrated = useRef(false);

  const clearSession = useCallback(() => {
    writeToken(ACCESS_KEY, "");
    writeToken(REFRESH_KEY, "");
    setUser(null);
    setStatus("anonymous");
  }, []);

  const tryRefresh = useCallback((): Promise<boolean> => {
    if (refreshing.current) return refreshing.current;
    const run = async (): Promise<boolean> => {
      const refreshToken = readToken(REFRESH_KEY);
      if (!refreshToken) {
        clearSession();
        return false;
      }
      try {
        const body = await request<{ accessToken: string; refreshToken: string }>("POST", "/api/v1/auth/refresh", { json: { refreshToken } });
        writeToken(ACCESS_KEY, body.accessToken);
        writeToken(REFRESH_KEY, body.refreshToken);
        setUser(await request<User>("GET", "/api/v1/auth/me", { token: body.accessToken }));
        setStatus("authenticated");
        return true;
      } catch {
        clearSession();
        return false;
      }
    };
    refreshing.current = run().finally(() => {
      refreshing.current = null;
    });
    return refreshing.current;
  }, [clearSession]);

  // Runs once per page load: rehydrate from the stored access token.
  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;
    const token = readToken(ACCESS_KEY);
    if (!token) {
      setStatus("anonymous");
      return;
    }
    request<User>("GET", "/api/v1/auth/me", { token })
      .then((me) => {
        setUser(me);
        setStatus("authenticated");
      })
      .catch(() => tryRefresh());
  }, [tryRefresh]);

  useEffect(() => {
    if (status !== "authenticated") return;
    const id = window.setInterval(() => void tryRefresh(), PROACTIVE_REFRESH_MS);
    return () => window.clearInterval(id);
  }, [status, tryRefresh]);

  // Synchronize authentication status and token rotation across open browser tabs.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === ACCESS_KEY && e.newValue) {
        request<User>("GET", "/api/v1/auth/me", { token: e.newValue })
          .then((me) => {
            setUser(me);
            setStatus("authenticated");
          })
          .catch(() => {});
      } else if (e.key === REFRESH_KEY && !e.newValue) {
        setUser(null);
        setStatus("anonymous");
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const withAuth = useCallback(
    async <R,>(call: (token: string) => Promise<R>): Promise<R> => {
      const tokenUsed = readToken(ACCESS_KEY);
      try {
        return await call(tokenUsed);
      } catch (exc) {
        if (exc instanceof ApiError && exc.isAuth) {
          // Another request may already have rotated the token: retry with the
          // current one instead of replaying (and reusing) the stale refresh token.
          if (readToken(ACCESS_KEY) !== tokenUsed || (await tryRefresh())) return call(readToken(ACCESS_KEY));
          clearSession();
        }
        throw exc;
      }
    },
    [tryRefresh, clearSession],
  );

  const api = useCallback<AuthContextValue["api"]>(
    (method, path, opts = {}) => withAuth((token) => request(method, path, { ...opts, token })),
    [withAuth],
  );
  const apiBlob = useCallback<AuthContextValue["apiBlob"]>((path, opts = {}) => withAuth((token) => getBlob(path, { ...opts, token })), [withAuth]);

  const login = useCallback<AuthContextValue["login"]>(async ({ email, password, mfaCode, mfaRecoveryCode }) => {
    try {
      const resp = await request<LoginResponse>("POST", "/api/v1/auth/login", {
        json: {
          email,
          password,
          ...(mfaCode ? { mfaCode } : {}),
          ...(mfaRecoveryCode ? { mfaRecoveryCode } : {}),
        },
      });
      writeToken(ACCESS_KEY, resp.accessToken);
      writeToken(REFRESH_KEY, resp.refreshToken);
      setUser(resp.user);
      setStatus("authenticated");
      return { mfaRequired: false };
    } catch (exc) {
      if (exc instanceof ApiError && exc.code === "MFA_REQUIRED") return { mfaRequired: true };
      throw exc;
    }
  }, []);

  const setSession = useCallback((resp: LoginResponse) => {
    writeToken(ACCESS_KEY, resp.accessToken);
    writeToken(REFRESH_KEY, resp.refreshToken);
    setUser(resp.user);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = readToken(REFRESH_KEY);
    try {
      await request("POST", "/api/v1/auth/logout", { token: readToken(ACCESS_KEY), json: refreshToken ? { refreshToken } : {} });
    } catch {
      /* signing out locally is what matters */
    }
    clearSession();
  }, [clearSession]);

  const reloadUser = useCallback(async () => {
    setUser(await api<User>("GET", "/api/v1/auth/me"));
  }, [api]);

  const permissions = useMemo(() => user?.permissions ?? [], [user]);
  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      permissions,
      can: (p) => permits(permissions, p),
      canAny: (ps) => ps.some((p) => permits(permissions, p)),
      login,
      setSession,
      logout,
      api,
      apiBlob,
      reloadUser,
    }),
    [status, user, permissions, login, setSession, logout, api, apiBlob, reloadUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
