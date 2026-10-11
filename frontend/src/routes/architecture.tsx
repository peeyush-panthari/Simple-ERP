/**
 * System status - the first page to open when something looks wrong: the
 * health of this deployment's own dependencies, plus a static
 * rewrite-progress map of the modules being ported.
 */
import { Shell } from "@/components/erp/shell";
import { Badge, DataTable, Forbidden, InlineError, PageHeader, Panel } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { useApiQuery } from "@/lib/hooks";

interface Health {
  healthy?: boolean | null;
  enabled?: boolean;
  backend?: string;
  available?: boolean;
  engine?: string;
}

interface Status {
  checks: Record<string, Health>;
  modules: { key: string; label: string; status: string }[];
  modulesDone: number;
  modulesTotal: number;
}

function HealthCard({ label, ok, detail }: { label: string; ok: boolean | null | undefined; detail?: string }) {
  return (
    <div className="panel p-4" style={{ minWidth: "14rem", flex: "1 1 14rem" }}>
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-[var(--muted-foreground)]">{label}</span>
        {ok === null || ok === undefined ? <Badge>not in use</Badge> : <Badge color={ok ? "green" : "red"}>{ok ? "healthy" : "unavailable"}</Badge>}
      </div>
      {detail ? <p className="mt-1 text-sm font-medium">{detail}</p> : null}
    </div>
  );
}

function Content() {
  const { data, error } = useApiQuery<Status>("/api/v1/system-status");
  const c = data?.checks;
  return (
    <div className="flex w-full flex-col gap-4">
      <PageHeader fit
        eyebrow="Overview"
        title="System status"
        description="The health of this process's own dependencies, and how much of the Node → Python rewrite is done. What to open first when something looks wrong."
      />
      <InlineError message={error?.message} />
      <div className="flex w-full flex-wrap gap-4">
        <HealthCard label="Database" ok={c?.database?.healthy} />
        <HealthCard label="Document storage" ok={c?.documentStorage?.healthy} detail={c?.documentStorage?.backend} />
        <HealthCard label="PDF engine" ok={c?.pdfEngine?.available} detail={c?.pdfEngine?.engine} />
        <HealthCard label="Mail transport" ok={c?.mailTransport?.healthy} />
        <HealthCard label="Redis" ok={c?.redis?.enabled ? c.redis.healthy : null} />
        <HealthCard label="RabbitMQ" ok={c?.rabbitmq?.enabled ? c.rabbitmq.healthy : null} />
      </div>
      <Panel
        title="Rewrite progress"
        className="w-full"
        aside={<span className="text-sm text-[var(--muted-foreground)]">{data?.modulesDone ?? 0} / {data?.modulesTotal ?? 0} modules done</span>}
      >
        <div className="w-full px-4 py-4">
          <DataTable columns={["Module", "Status"]} fit>
            {(data?.modules ?? []).map((m) => (
              <tr key={m.key}>
                <td>{m.label}</td>
                <td>{m.status === "done" ? <Badge color="green">Done</Badge> : m.status === "not_started" ? <Badge color="amber">Not started</Badge> : <Badge>N/A</Badge>}</td>
              </tr>
            ))}
          </DataTable>
        </div>
      </Panel>
    </div>
  );
}

export default function ArchitecturePage() {
  const { can } = useAuth();
  return <Shell>{can("analytics:read") ? <Content /> : <Forbidden permission="analytics:read" />}</Shell>;
}
