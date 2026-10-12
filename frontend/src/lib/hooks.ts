import { keepPreviousData, useQuery, type UseQueryOptions } from "@tanstack/react-query";
import { useCallback, useEffect, useState, useRef } from "react";
import { useAuth } from "@/lib/auth";
import { ApiError, type Params } from "@/lib/api";

/** Retry predicate: only retry transient network drops (status 0) and 503 Service Unavailable, max 2 attempts. */
export function shouldRetryApiQuery(failureCount: number, error: unknown): boolean {
  if (failureCount >= 2) return false;
  return error instanceof ApiError && (error.status === 0 || error.status === 503);
}

/** GET a path with the authorised client; the cache key is the path + params. */
export function useApiQuery<T>(path: string, params?: Params, options?: Partial<Omit<UseQueryOptions<T>, "queryKey" | "queryFn">>) {
  const { api } = useAuth();
  return useQuery<T>({
    queryKey: [path, params ?? {}],
    queryFn: ({ signal }) => api<T>("GET", path, { params, signal }),
    placeholderData: keepPreviousData,
    retry: shouldRetryApiQuery,
    ...options,
  });
}

/** A value that trails `value` by `delay` ms - keeps a search box from firing a request per keystroke. */
export function useDebounced<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

export interface ListResponse<T> {
  data: T[];
  meta?: { page: number; limit: number; total: number; pages: number };
}

/** Saves a Blob the way rx.download did: a temporary anchor click. */
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Runs an async action tracking `busy` and the ApiError detail - the shape every dialog/button handler needs. */
export function useAsyncAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true);
    setError("");
    try {
      return await fn();
    } catch (exc) {
      if (isMounted.current) {
        setError(exc instanceof ApiError ? exc.detail : exc instanceof Error ? exc.message : String(exc));
      }
      return undefined;
    } finally {
      if (isMounted.current) {
        setBusy(false);
      }
    }
  }, []);
  return { run, busy, error, setError };
}
