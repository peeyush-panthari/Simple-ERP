/** Generated/uploaded document list, download and reprint. */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Shell } from "@/components/erp/shell";
import { ActionButton, DataTable, DesktopOnly, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, PageHeader, Pill } from "@/components/erp/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import * as format from "@/lib/format";
import { downloadBlob, useApiQuery, useDebounced, type ListResponse } from "@/lib/hooks";

interface Doc {
  id: string;
  filename: string;
  kind: string;
  template?: string | null;
  relatedType?: string | null;
  relatedId?: string | null;
  scanStatus: string;
  createdAt?: string;
}

function Content() {
  const { api, apiBlob } = useAuth();
  const qc = useQueryClient();
  const [filters, setFilters] = useState({ relatedType: "", relatedId: "", template: "", q: "" });
  const debounced = useDebounced(filters);
  const [actionError, setActionError] = useState("");
  const { data, error } = useApiQuery<ListResponse<Doc>>("/api/v1/documents", { limit: 100, ...debounced });
  const items = data?.data ?? [];

  const run = async (fn: () => Promise<unknown>) => {
    setActionError("");
    try {
      await fn();
    } catch (exc) {
      setActionError(exc instanceof ApiError ? exc.detail : String(exc));
    }
  };
  const download = (d: Doc) =>
    run(async () => {
      const { blob } = await apiBlob(`/api/v1/documents/${d.id}/download`);
      downloadBlob(blob, d.filename);
    });
  const reprint = (d: Doc) =>
    run(async () => {
      await api("POST", `/api/v1/documents/${d.id}/reprint`);
      await qc.invalidateQueries({ queryKey: ["/api/v1/documents"] });
    });

  const related = (d: Doc) => (d.relatedType ? `${d.relatedType} / ${d.relatedId}` : "—");
  const actions = (d: Doc) => (
    <>
      <ActionButton size="sm" tone="ghost" onClick={() => download(d)}>Download</ActionButton>
      {d.kind === "generated" && <ActionButton size="sm" tone="ghost" onClick={() => reprint(d)}>Reprint</ActionButton>}
    </>
  );
  const input = (key: keyof typeof filters, placeholder: string, width: string) => {
    const id = `doc-filter-${key}`;
    return (
      <div key={key}>
        <label htmlFor={id} className="sr-only">{placeholder}</label>
        <input id={id} className="search-input" style={{ width }} placeholder={placeholder} value={filters[key]} onChange={(e) => setFilters({ ...filters, [key]: e.target.value })} />
      </div>
    );
  };

  return (
    <div className="flex w-full flex-col gap-4">
      <PageHeader fit eyebrow="Platform" title="Documents" />
      <InlineError message={actionError || error?.message} />
      <div className="flex flex-wrap gap-2">
        {input("relatedType", "Related type", "180px")}
        {input("relatedId", "Related ID", "220px")}
        {input("template", "Template", "180px")}
        {input("q", "Search filename", "220px")}
      </div>
      <DesktopOnly className="w-full">
        <DataTable columns={["Filename", "Kind", "Template", "Related", "Scan", "Created", "Actions"]} fit>
          {items.map((d) => (
            <tr key={d.id}>
              <td>{d.filename}</td>
              <td>{d.kind}</td>
              <td>{d.template}</td>
              <td>{related(d)}</td>
              <td><Pill>{d.scanStatus}</Pill></td>
              <td>{format.dateTime(d.createdAt)}</td>
              <td><div className="flex gap-2">{actions(d)}</div></td>
            </tr>
          ))}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {items.map((d) => (
          <MobileRecordCard key={d.id} actions={actions(d)}>
            <MobileRecordRow label="Filename" value={d.filename} />
            <MobileRecordRow label="Kind" value={d.kind} />
            <MobileRecordRow label="Template" value={d.template} />
            <MobileRecordRow label="Related" value={related(d)} />
            <MobileRecordRow label="Scan" value={<Pill>{d.scanStatus}</Pill>} />
            <MobileRecordRow label="Created" value={format.dateTime(d.createdAt)} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
    </div>
  );
}

export default function DocumentsPage() {
  const { can } = useAuth();
  return <Shell>{can("document:read") ? <Content /> : <Forbidden permission="document:read" />}</Shell>;
}
