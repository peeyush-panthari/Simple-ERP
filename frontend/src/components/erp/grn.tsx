/** GRN pieces shared by the GRN & QC page and the QC route. */
import { Pill } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { downloadBlob } from "@/lib/hooks";
import { toneFor } from "@/lib/status";

const GRN_STATUS_LABELS: Record<string, string> = { under_qc: "Under QC", posted: "Posted", rejected: "Rejected", cancelled: "Cancelled" };
export const grnStatusLabel = (value: string) => GRN_STATUS_LABELS[value] ?? value;

/** Tone comes from the raw status, the label from the humanised map, so a GRN and its items read the same at every level. */
export function GrnStatusPill({ status }: { status: string }) {
  return <Pill tone={toneFor(status)}>{grnStatusLabel(status)}</Pill>;
}

export interface GrnRef {
  id: string;
  number: string;
}

/** The two per-GRN sticker downloads: every QR as a zip, and one sticker-sheet PDF (HTML when no PDF engine). */
export function useQrDownloads() {
  const { apiBlob } = useAuth();
  return {
    zip: async (g: GrnRef) => {
      const { blob } = await apiBlob(`/api/v1/grns/${g.id}/qr-codes`);
      downloadBlob(blob, `${g.number}-qr-codes.zip`);
    },
    pdf: async (g: GrnRef) => {
      const { blob, contentType } = await apiBlob(`/api/v1/grns/${g.id}/qr-codes/pdf`);
      downloadBlob(blob, `${g.number}-qr-codes.${contentType === "application/pdf" ? "pdf" : "html"}`);
    },
  };
}
