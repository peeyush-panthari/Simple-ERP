/**
 * Scanning helpers (ports of ui_kit.py's scan_to_jump_box / scan_to_add_button /
 * hardware_scan_listener). Scanning itself is server-side (the API decodes QR
 * images and resolves our own inventory-item QR URLs); the browser only supplies
 * a camera photo or relays a hardware (HID keyboard-emulation) scanner's keystrokes.
 */
import { Camera } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ActionButton } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

/**
 * A text input a hardware scanner types into (decoded text + Enter). On Enter the text
 * is resolved via POST /inventory-items/resolve-scan and the app jumps to that item.
 */
export function ScanToJumpBox({ placeholder = "Scan to jump to an Inventory ID…" }: { placeholder?: string }) {
  const { api } = useAuth();
  const navigate = useNavigate();
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    const text = value.trim();
    if (!text) return;
    setBusy(true);
    try {
      const item = await api<{ id: string }>("POST", "/api/v1/inventory-items/resolve-scan", { json: { text } });
      setValue("");
      navigate(`/inventory-item/${item.id}`);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.detail : String(exc));
    } finally {
      setBusy(false);
    }
  };
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter") void submit();
  };

  return (
    <div className="flex flex-col items-start gap-1">
      <label htmlFor="scan-jump-input" className="sr-only">Scan to jump to an Inventory ID</label>
      <input
        id="scan-jump-input"
        className="ui-input"
        style={{ width: "20rem" }}
        placeholder={placeholder}
        value={value}
        disabled={busy}
        onChange={(e) => {
          setValue(e.target.value);
          setError("");
        }}
        onKeyDown={onKeyDown}
      />
      {error && <p className="text-xs text-[var(--destructive)]">{error}</p>}
    </div>
  );
}

/** A photo button that opens the device camera directly on a phone (file input with `capture`). */
export function ScanToAddButton({ onPhoto, busy, label = "Scan to Add", busyLabel = "Scanning…" }: { onPhoto: (file: File) => void; busy: boolean; label?: string; busyLabel?: string }) {
  const ref = useRef<HTMLInputElement>(null);
  const inputId = useRef(`scan-photo-${Math.random().toString(36).substring(2, 9)}`);
  return (
    <div>
      <ActionButton size="sm" tone="ghost" loading={busy} onClick={() => ref.current?.click()}>
        <Camera size={14} />
        {busy ? busyLabel : label}
      </ActionButton>
      <label htmlFor={inputId.current} className="sr-only">Upload or capture photo to add</label>
      <input
        id={inputId.current}
        ref={ref}
        type="file"
        aria-label="Upload or capture photo to add"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) onPhoto(file);
        }}
      />
    </div>
  );
}

const MAX_GAP_MS = 60;
const MIN_LENGTH = 15;

const isEditable = (el: Element | null) => {
  if (!el) return false;
  const tag = el.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select" || (el as HTMLElement).isContentEditable;
};

/**
 * Passive hardware-scanner capture. A HID scanner types a QR's text as very fast keystrokes
 * ending in Enter; this listens at document level (no field needs focus), buffers only while
 * no editable element is focused - so it never steals keystrokes - and hands over a burst
 * that ends in Enter and looks like one of our /inventory-item/{uuid} QR URLs.
 */
export function useHardwareScanner(onScan: (text: string) => void, enabled = true) {
  const handler = useRef(onScan);
  handler.current = onScan;
  useEffect(() => {
    if (!enabled) return;
    let buffer = "";
    let last = 0;
    const onKeyDown = (e: globalThis.KeyboardEvent) => {
      if (isEditable(document.activeElement)) {
        buffer = "";
        return;
      }
      const now = Date.now();
      if (now - last > MAX_GAP_MS) buffer = "";
      last = now;
      if (e.key === "Enter") {
        if (buffer.length >= MIN_LENGTH && buffer.includes("inventory-item")) handler.current(buffer);
        buffer = "";
        return;
      }
      if (e.key.length === 1) buffer += e.key;
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [enabled]);
}
