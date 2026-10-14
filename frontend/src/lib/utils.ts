import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { ApiError } from "@/lib/api";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Extracts a human-readable error message from an unknown caught exception. */
export function errMsg(exc: unknown): string {
  if (exc instanceof ApiError) return exc.detail;
  if (exc instanceof Error) return exc.message;
  return String(exc || "An unexpected error occurred");
}

export const errText = errMsg;
