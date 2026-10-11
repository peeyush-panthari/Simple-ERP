/**
 * Session behaviour: hydration, single-flight refresh-token rotation (the
 * backend revokes every session if a rotated refresh token is reused, so
 * concurrent 401s must share ONE refresh), permission gating, sign-out.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "@/lib/auth";
import { Forbidden } from "@/components/erp/ui";

const USER = { id: "u1", email: "a@b.test", displayName: "Ada Lovelace", roles: [{ name: "Admin" }], permissions: ["order:read"], warehouseIds: null, factoryIds: null };

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

let calls: { method: string; path: string; auth: string | null }[];
type Handler = (path: string, init: RequestInit) => Response | Promise<Response>;

function mockFetch(handler: Handler) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const path = String(input);
      calls.push({ method: init.method ?? "GET", path, auth: (init.headers as Record<string, string> | undefined)?.Authorization ?? null });
      return handler(path, init);
    }),
  );
}

function Probe({ onReady }: { onReady: (ctx: ReturnType<typeof useAuth>) => void }) {
  const ctx = useAuth();
  onReady(ctx);
  return (
    <div>
      <span data-testid="status">{ctx.status}</span>
      <span data-testid="name">{ctx.user?.displayName ?? ""}</span>
      <span data-testid="can-order">{String(ctx.can("order:read"))}</span>
      <span data-testid="can-ship">{String(ctx.can("order:ship"))}</span>
    </div>
  );
}

function setup(onReady: (ctx: ReturnType<typeof useAuth>) => void = () => {}) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <AuthProvider>
          <Probe onReady={onReady} />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("AuthProvider", () => {
  it("is anonymous with no stored token and never calls the API", async () => {
    mockFetch(() => json(500, {}));
    setup();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
    expect(calls).toHaveLength(0);
  });


  it("rehydrates the user from a stored access token", async () => {
    localStorage.setItem("axon.accessToken", "tok");
    mockFetch(() => json(200, USER));
    setup();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    expect(screen.getByTestId("name")).toHaveTextContent("Ada Lovelace");
    expect(calls[0]).toMatchObject({ path: "/api/v1/auth/me", auth: "Bearer tok" });
  });

  it("recovers an expired access token through the refresh token", async () => {
    localStorage.setItem("axon.accessToken", "expired");
    localStorage.setItem("axon.refreshToken", "r1");
    mockFetch((path, init) => {
      if (path.endsWith("/auth/refresh")) return json(200, { accessToken: "fresh", refreshToken: "r2" });
      const bearer = (init.headers as Record<string, string>).Authorization;
      return bearer === "Bearer fresh" ? json(200, USER) : json(401, { title: "expired" });
    });
    setup();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    expect(localStorage.getItem("axon.accessToken")).toBe("fresh");
    expect(localStorage.getItem("axon.refreshToken")).toBe("r2");
  });

  it("clears the session when the refresh token is rejected", async () => {
    localStorage.setItem("axon.accessToken", "expired");
    localStorage.setItem("axon.refreshToken", "dead");
    mockFetch(() => json(401, { title: "no" }));
    setup();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
    expect(localStorage.getItem("axon.refreshToken")).toBeNull();
  });

  it("shares ONE refresh across concurrent 401s (a second refresh would replay a rotated token)", async () => {
    localStorage.setItem("axon.accessToken", "good");
    localStorage.setItem("axon.refreshToken", "r1");
    let refreshes = 0;
    let rotated = false;
    mockFetch(async (path, init) => {
      if (path.endsWith("/auth/refresh")) {
        refreshes += 1;
        await new Promise((r) => setTimeout(r, 20));
        rotated = true;
        return json(200, { accessToken: "fresh", refreshToken: "r2" });
      }
      const bearer = (init.headers as Record<string, string>).Authorization;
      if (path.endsWith("/auth/me")) return json(200, USER);
      return rotated && bearer === "Bearer fresh" ? json(200, { ok: path }) : json(401, { title: "expired" });
    });
    let ctx!: ReturnType<typeof useAuth>;
    setup((c) => (ctx = c));
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));

    const results = await Promise.all([ctx.api("GET", "/api/v1/a"), ctx.api("GET", "/api/v1/b"), ctx.api("GET", "/api/v1/c")]);
    expect(results).toEqual([{ ok: "/api/v1/a" }, { ok: "/api/v1/b" }, { ok: "/api/v1/c" }]);
    expect(refreshes).toBe(1);
  });

  it("exposes permission checks including wildcards", async () => {
    localStorage.setItem("axon.accessToken", "tok");
    mockFetch(() => json(200, { ...USER, permissions: ["order:read"] }));
    setup();
    await waitFor(() => expect(screen.getByTestId("can-order")).toHaveTextContent("true"));
    expect(screen.getByTestId("can-ship")).toHaveTextContent("false");
  });

  it("login returns mfaRequired instead of throwing when a second factor is needed", async () => {
    mockFetch(() => json(401, { code: "MFA_REQUIRED", title: "MFA required" }));
    let ctx!: ReturnType<typeof useAuth>;
    setup((c) => (ctx = c));
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
    await expect(ctx.login({ email: "a@b.test", password: "x" })).resolves.toEqual({ mfaRequired: true });
    expect(localStorage.getItem("axon.accessToken")).toBeNull();
  });

  it("login surfaces the problem+json detail, including per-field errors", async () => {
    mockFetch(() => json(400, { title: "Validation Failed", detail: "Validation failed", code: "VALIDATION_FAILED", errors: [{ field: "email", message: "not an email" }] }));
    let ctx!: ReturnType<typeof useAuth>;
    setup((c) => (ctx = c));
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
    await expect(ctx.login({ email: "x", password: "y" })).rejects.toThrow("Validation failed: email: not an email");
  });

  it("logout clears tokens even if the server call fails", async () => {
    localStorage.setItem("axon.accessToken", "tok");
    localStorage.setItem("axon.refreshToken", "r1");
    mockFetch((path) => (path.endsWith("/auth/logout") ? json(500, {}) : json(200, USER)));
    let ctx!: ReturnType<typeof useAuth>;
    setup((c) => (ctx = c));
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    await ctx.logout();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
    expect(localStorage.getItem("axon.accessToken")).toBeNull();
  });
});

describe("Forbidden", () => {
  it("names the missing permission for a signed-in user", async () => {
    localStorage.setItem("axon.accessToken", "tok");
    mockFetch(() => json(200, USER));
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <AuthProvider>
            <Forbidden permission="finance:read" />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText("You do not have access to this module")).toBeInTheDocument());
    expect(screen.getByText("finance:read")).toBeInTheDocument();
  });

  it("offers sign-in instead when the session has expired", async () => {
    mockFetch(() => json(401, {}));
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <AuthProvider>
            <Forbidden permission="finance:read" />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText("Your session has expired")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Sign in again" })).toHaveAttribute("href", "/login");
  });
});
