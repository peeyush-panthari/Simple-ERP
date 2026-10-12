import { describe, expect, it, vi } from "vitest";
import { shouldRetryApiQuery } from "@/lib/hooks";
import { ApiError } from "@/lib/api";
import { fetchAllRoles } from "@/routes/users";

describe("Phase 2: Network error retry policy (shouldRetryApiQuery)", () => {
  it("retries on status 0 (network drop) on first failure", () => {
    const netErr = new ApiError(0, { title: "Network error" });
    expect(shouldRetryApiQuery(0, netErr)).toBe(true);
    expect(shouldRetryApiQuery(1, netErr)).toBe(true);
  });

  it("retries on status 503 (Service Unavailable) on first failure", () => {
    const srvErr = new ApiError(503, { title: "Service Unavailable" });
    expect(shouldRetryApiQuery(0, srvErr)).toBe(true);
    expect(shouldRetryApiQuery(1, srvErr)).toBe(true);
  });

  it("does not retry once failureCount reaches 2", () => {
    const netErr = new ApiError(0, { title: "Network error" });
    expect(shouldRetryApiQuery(2, netErr)).toBe(false);
    expect(shouldRetryApiQuery(3, netErr)).toBe(false);
  });

  it("does not retry 4xx errors (400, 401, 403, 404, 422)", () => {
    for (const status of [400, 401, 403, 404, 422]) {
      const err = new ApiError(status, { title: "Error" });
      expect(shouldRetryApiQuery(0, err)).toBe(false);
    }
  });

  it("does not retry non-ApiError errors", () => {
    expect(shouldRetryApiQuery(0, new Error("Generic error"))).toBe(false);
    expect(shouldRetryApiQuery(0, "some string")).toBe(false);
  });
});

describe("Phase 2: Infinite loop circuit breaker (fetchAllRoles)", () => {
  it("fetches single page correctly", async () => {
    const mockApi = vi.fn().mockResolvedValue({
      data: [{ id: "r1", name: "Admin", permissions: [], userCount: 1 }],
      meta: { page: 1, limit: 200, total: 1, pages: 1 },
    });
    const roles = await fetchAllRoles(mockApi);
    expect(roles).toHaveLength(1);
    expect(roles[0].name).toBe("Admin");
    expect(mockApi).toHaveBeenCalledTimes(1);
  });

  it("paginates across multiple pages until pages limit", async () => {
    const mockApi = vi.fn().mockImplementation((_method, _path, opts) => {
      const page = opts.params.page;
      return Promise.resolve({
        data: [{ id: `r${page}`, name: `Role ${page}`, permissions: [], userCount: 1 }],
        meta: { page, limit: 200, total: 3, pages: 3 },
      });
    });
    const roles = await fetchAllRoles(mockApi);
    expect(roles).toHaveLength(3);
    expect(mockApi).toHaveBeenCalledTimes(3);
  });

  it("breaks early if empty data is returned", async () => {
    const mockApi = vi.fn().mockResolvedValue({
      data: [],
      meta: { page: 1, limit: 200, total: 10, pages: 5 },
    });
    const roles = await fetchAllRoles(mockApi);
    expect(roles).toHaveLength(0);
    expect(mockApi).toHaveBeenCalledTimes(1);
  });

  it("breaks at MAX_PAGES (50) to prevent infinite loops even if backend returns infinite pages", async () => {
    const mockApi = vi.fn().mockImplementation((_method, _path, opts) => {
      const page = opts.params.page;
      return Promise.resolve({
        data: [{ id: `r${page}`, name: `Role ${page}`, permissions: [], userCount: 1 }],
        meta: { page, limit: 200, total: 9999, pages: 9999 },
      });
    });
    const roles = await fetchAllRoles(mockApi);
    expect(roles).toHaveLength(50);
    expect(mockApi).toHaveBeenCalledTimes(50);
  });
});
