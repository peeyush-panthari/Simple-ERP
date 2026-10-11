/** Click feedback: one button look, a spinner while work is running (no double submit), the request activity counter, and the account menu. */
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Shell } from "@/components/erp/shell";
import { ActionButton, TopProgress } from "@/components/erp/ui";
import { activeRequests, beginRequest } from "@/lib/activity";
import { request } from "@/lib/api";
import { AuthProvider } from "@/lib/auth";

afterEach(() => vi.unstubAllGlobals());

describe("buttons", () => {
  it("every tone is the same colour class", () => {
    render(<><ActionButton>A</ActionButton><ActionButton tone="ghost">B</ActionButton><ActionButton tone="danger">C</ActionButton></>);
    const cls = ["A", "B", "C"].map((n) => screen.getByRole("button", { name: n }).className.split(" ").filter((c) => c.startsWith("action-btn-") && c !== "action-btn-sm"));
    expect(cls[1]).toEqual(cls[0]);
    expect(cls[2]).toEqual(cls[0]);
  });

  it("shows a spinner while an async click runs and ignores a second click", async () => {
    let finish: () => void = () => {};
    const onClick = vi.fn(() => new Promise<void>((r) => (finish = r)));
    render(<ActionButton onClick={onClick}>Save</ActionButton>);
    const btn = screen.getByRole("button", { name: "Save" });
    await userEvent.click(btn);
    expect(btn).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    await userEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
    await act(async () => finish());
    await waitFor(() => expect(btn).not.toHaveAttribute("aria-busy"));
    expect(screen.queryByRole("status")).toBeNull();
    await userEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it("a button that is told it is loading does not fire", async () => {
    const onClick = vi.fn();
    render(<ActionButton loading onClick={onClick}>Create</ActionButton>);
    await userEvent.click(screen.getByRole("button", { name: /Create/ }));
    expect(onClick).not.toHaveBeenCalled();
  });

  it("a failing async click still comes back to normal", async () => {
    render(<ActionButton onClick={() => Promise.reject(new Error("nope")).catch(() => {})}>Go</ActionButton>);
    const btn = screen.getByRole("button", { name: "Go" });
    await userEvent.click(btn);
    await waitFor(() => expect(btn).not.toHaveAttribute("aria-busy"));
  });
});

describe("request activity", () => {
  it("counts requests in flight and always lets go, even on an error", async () => {
    let release: (r: Response) => void = () => {};
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((r) => (release = r))));
    const p = request("GET", "/api/v1/x");
    expect(activeRequests()).toBe(1);
    release(new Response("{}", { status: 500, headers: { "content-type": "application/json" } }));
    await expect(p).rejects.toBeTruthy();
    expect(activeRequests()).toBe(0);
    const end = beginRequest();
    end();
    end();
    expect(activeRequests()).toBe(0);
  });

  it("the top bar appears for slow requests only", async () => {
    vi.useFakeTimers();
    render(<TopProgress />);
    let end: () => void = () => {};
    act(() => {
      end = beginRequest();
    });
    await act(async () => void vi.advanceTimersByTime(60));
    expect(screen.queryByRole("progressbar")).toBeNull();
    await act(async () => void vi.advanceTimersByTime(200));
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    act(() => end());
    await act(async () => void vi.advanceTimersByTime(400));
    expect(screen.queryByRole("progressbar")).toBeNull();
    vi.useRealTimers();
  });
});

describe("account menu", () => {
  const USER = { id: "u1", email: "ada@example.test", displayName: "Ada Lovelace", roles: [{ name: "Admin" }], permissions: ["*"], warehouseIds: null, factoryIds: null };

  function mount() {
    const calls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      calls.push(path);
      if (path.endsWith("/auth/me")) return new Response(JSON.stringify(USER), { status: 200, headers: { "content-type": "application/json" } });
      return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
    }));
    localStorage.clear();
    localStorage.setItem("axon.accessToken", "tok");
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/home"]}>
          <AuthProvider>
            <Routes>
              <Route path="/home" element={<Shell>home page</Shell>} />
              <Route path="/profile" element={<p>profile page</p>} />
              <Route path="/login" element={<p>login page</p>} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    return calls;
  }

  it("has no separate logout button; the user button opens Profile and Logout", async () => {
    mount();
    const trigger = await screen.findByRole("button", { name: /Account/i });
    expect(screen.queryByTitle("Sign out")).toBeNull();
    expect(screen.queryByRole("menu")).toBeNull();
    await userEvent.click(trigger);
    const items = (await screen.findAllByRole("menuitem")).map((i) => i.textContent);
    expect(items).toEqual(["ProfileMFA & password", "Logout"]);
  });

  it("Profile goes to the profile page", async () => {
    mount();
    await userEvent.click(await screen.findByRole("button", { name: /Account/i }));
    await userEvent.click(await screen.findByRole("menuitem", { name: /Profile/ }));
    expect(await screen.findByText("profile page")).toBeInTheDocument();
  });

  it("Logout signs out and lands on the login page", async () => {
    const calls = mount();
    await userEvent.click(await screen.findByRole("button", { name: /Account/i }));
    await userEvent.click(await screen.findByRole("menuitem", { name: /Logout/ }));
    expect(await screen.findByText("login page")).toBeInTheDocument();
    expect(calls.some((c) => c.endsWith("/auth/logout"))).toBe(true);
  });
});

describe("status colours and the shared Bulk Upload button", () => {
  it("active is green, inactive and deactivated are red", async () => {
    const { toneFor } = await import("@/lib/status");
    expect(toneFor("active")).toBe("success");
    expect(toneFor("inactive")).toBe("destructive");
    expect(toneFor("Deactivated")).toBe("destructive");
    expect(toneFor("constrained")).toBe("warning");
  });

  it("every Bulk Upload button is the same button", async () => {
    const { BulkUploadButton } = await import("@/components/erp/bulk-upload");
    const click = vi.fn();
    render(<><BulkUploadButton onClick={click} /><BulkUploadButton onClick={() => {}} label="Bulk Upload Transfers" /></>);
    const [a, b] = screen.getAllByRole("button");
    expect(a.className).toBe(b.className);
    expect(a.querySelector("svg")).not.toBeNull();
    expect(a).toHaveTextContent("Bulk Upload");
    await userEvent.click(a);
    expect(click).toHaveBeenCalledOnce();
  });

  it("the loading overlay waits half a second and only reacts to reads", async () => {
    vi.useFakeTimers();
    const { LoadingOverlay } = await import("@/components/erp/ui");
    render(<LoadingOverlay />);
    let end: () => void = () => {};
    act(() => {
      end = beginRequest(true);
    });
    await act(async () => void vi.advanceTimersByTime(300));
    expect(screen.queryByRole("status")).toBeNull();
    await act(async () => void vi.advanceTimersByTime(300));
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    act(() => end());
    await act(async () => void vi.advanceTimersByTime(300));
    expect(screen.queryByRole("status")).toBeNull();
    let write: () => void = () => {};
    act(() => {
      write = beginRequest(false);
    });
    await act(async () => void vi.advanceTimersByTime(1500));
    expect(screen.queryByRole("status")).toBeNull();
    act(() => write());
    vi.useRealTimers();
  });
});
