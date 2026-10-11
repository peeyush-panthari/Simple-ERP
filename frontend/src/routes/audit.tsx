/** Append-only audit log page. */
import { Shell } from "@/components/erp/shell";
import { DataTable, DesktopOnly, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, PageHeader } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import * as format from "@/lib/format";
import { useApiQuery, type ListResponse } from "@/lib/hooks";

interface Entry {
  id: string;
  created_at?: string;
  actor_email?: string | null;
  action: string;
  entity_type?: string | null;
  entity_id?: string | null;
  reason?: string | null;
}

const entity = (e: Entry) => `${e.entity_type ?? "None"} / ${e.entity_id ?? "None"}`;

function Content() {
  const { data, error } = useApiQuery<ListResponse<Entry>>("/api/v1/audit", { limit: 100 });
  const entries = data?.data ?? [];
  return (
    <div className="flex w-full flex-col gap-4">
      <PageHeader fit eyebrow="Platform" title="Audit trail" />
      <InlineError message={error?.message} />
      <DesktopOnly className="w-full">
        <DataTable columns={["When", "Actor", "Action", "Entity", "Reason"]} fit>
          {entries.map((e) => (
            <tr key={e.id}>
              <td>{format.dateTime(e.created_at)}</td>
              <td>{e.actor_email}</td>
              <td>{e.action}</td>
              <td>{entity(e)}</td>
              <td>{e.reason}</td>
            </tr>
          ))}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {entries.map((e) => (
          <MobileRecordCard key={e.id}>
            <MobileRecordRow label="When" value={format.dateTime(e.created_at)} />
            <MobileRecordRow label="Actor" value={e.actor_email} />
            <MobileRecordRow label="Action" value={e.action} />
            <MobileRecordRow label="Entity" value={entity(e)} />
            <MobileRecordRow label="Reason" value={e.reason} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
    </div>
  );
}

export default function AuditPage() {
  const { can } = useAuth();
  return <Shell>{can("audit:read") ? <Content /> : <Forbidden permission="audit:read" />}</Shell>;
}
