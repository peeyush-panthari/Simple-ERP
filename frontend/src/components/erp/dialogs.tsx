/** Small dialogs several pages share. */
import { useState, type FormEvent, type ReactNode } from "react";
import { ActionButton, InlineError, Modal, TextArea } from "@/components/erp/ui";
import { useAsyncAction } from "@/lib/hooks";

/**
 * "Why?" dialog: a required free-text reason (min length) sent to `onSubmit`.
 * Backs cancel / short-close / reject style actions. `onSubmit` throws to surface an error.
 */
export function ReasonDialog({
  title,
  description,
  confirmLabel,
  danger = true,
  minLength = 5,
  placeholder = "Reason (min 5 characters)",
  descriptionSize,
  onClose,
  onSubmit,
  children,
}: {
  title: string;
  description?: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  minLength?: number;
  placeholder?: string;
  descriptionSize?: "1" | "2" | "radix";
  onClose: () => void;
  onSubmit: (reason: string) => Promise<void>;
  children?: ReactNode;
}) {
  const { run, busy, error, setError } = useAsyncAction();
  const [reason, setReason] = useState("");
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (reason.length < minLength) return setError(`Reason must be at least ${minLength} characters`);
    const ok = await run(async () => {
      await onSubmit(reason);
      return true;
    });
    if (ok) onClose();
  };
  return (
    <Modal open onClose={onClose} title={title} description={description} descriptionSize={descriptionSize}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <InlineError message={error} />
        {children}
        <TextArea value={reason} onChange={(e) => setReason(e.target.value)} placeholder={placeholder} required />
        <div className="flex justify-end gap-2">
          <ActionButton tone="ghost" onClick={onClose}>Back</ActionButton>
          <ActionButton type="submit" tone={danger ? "danger" : "primary"} loading={busy}>{confirmLabel}</ActionButton>
        </div>
      </form>
    </Modal>
  );
}
