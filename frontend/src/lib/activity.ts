/** How many API requests are in flight right now - drives the top progress bar. Every request goes through `send` in api.ts. */
import { useSyncExternalStore } from "react";

let inFlight = 0;
let reads = 0; // GETs only: loading a page or its data (a save already has its own button spinner)
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export function beginRequest(isRead = false): () => void {
  inFlight += 1;
  if (isRead) reads += 1;
  emit();
  let done = false;
  return () => {
    if (done) return;
    done = true;
    inFlight = Math.max(0, inFlight - 1);
    if (isRead) reads = Math.max(0, reads - 1);
    emit();
  };
}

export const activeRequests = () => inFlight;

export function useActiveRequests(): number {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => inFlight,
    () => 0,
  );
}

export function useActiveReads(): number {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => reads,
    () => 0,
  );
}
