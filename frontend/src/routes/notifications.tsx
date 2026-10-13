/** Delivery log (list + retry) - no template or suppression management UI, matching the original. */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Shell } from "@/components/erp/shell";
import { ActionButton, DataTable, DesktopOnly, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, PageHeader, Badge } from "@/components/erp/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import * as format from "@/lib/format";
import { useApiQuery, type ListResponse } from "@/lib/hooks";

interface Entry {
  id: string;
  notificationId: string;
  outcome: string;
  provider?: string | null;
  attempt: number;
  detail?: string | null;
  createdAt?: string;
}

const outcomeColor = (o: string) => (o === "sent" ? "green" : o.includes("bounc") || o === "failed" ? "red" : "gray") as "green" | "red" | "gray";

function Content() {
  const { api } = useAuth();
  const qc = useQueryClient();
  const [actionError, setActionError] = useState("");
  const { data, error } = useApiQuery<ListResponse<Entry>>("/api/v1/delivery-logs", { limit: 100 });
  const items = data?.data ?? [];

  const retry = async (e: Entry) => {
    setActionError("");
    try {
      await api("POST", `/api/v1/notifications/${e.notificationId}/retry`);
      await qc.invalidateQueries({ queryKey: ["/api/v1/delivery-logs"] });
    } catch (exc) {
      setActionError(exc instanceof ApiError ? exc.detail : String(exc));
    }
  };
  const action = (e: Entry) => (e.outcome !== "sent" ? <ActionButton size="sm" tone="ghost" onClick={() => retry(e)}>Retry</ActionButton> : null);

  return (
    <div className="flex w-full flex-col gap-4">
      <PageHeader fit eyebrow="Platform" title="Notifications" />
      <InlineError message={actionError || error?.message} />
      <DesktopOnly className="w-full">
        <DataTable columns={["When", "Outcome", "Channel", "Attempt", "Detail", "Actions"]} fit>
          {items.map((e) => (
            <tr key={e.id}>
              <td>{format.dateTime(e.createdAt)}</td>
              <td><Badge color={outcomeColor(e.outcome)}>{e.outcome}</Badge></td>
              <td>{e.provider}</td>
              <td>{e.attempt}</td>
              <td>{e.detail}</td>
              <td>{action(e)}</td>
            </tr>
          ))}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {items.map((e) => (
          <MobileRecordCard key={e.id} actions={action(e)}>
            <MobileRecordRow label="When" value={format.dateTime(e.createdAt)} />
            <MobileRecordRow label="Outcome" value={<Badge color={outcomeColor(e.outcome)}>{e.outcome}</Badge>} />
            <MobileRecordRow label="Provider" value={e.provider} />
            <MobileRecordRow label="Attempt" value={e.attempt} />
            <MobileRecordRow label="Detail" value={e.detail} />
          </MobileRecordCard>
        ))}
      </MobileOnly>
    </div>
  );
}

export default function NotificationsPage() {
  const { can } = useAuth();
  return <Shell>{can("notification:read") ? <Content /> : <Forbidden permission="notification:read" />}</Shell>;
}
