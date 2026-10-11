/** Own-account page: multi-factor authentication, backup recovery codes, password, and active sessions. */
import { useQueryClient } from "@tanstack/react-query";
import { Copy, Check, Laptop, LogOut, Key } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useToast } from "@/components/erp/extras";
import { Shell } from "@/components/erp/shell";
import { ActionButton, DataTable, Field, InlineError, Modal, PageHeader, Panel, Pill, TextInput } from "@/components/erp/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApiQuery, useAsyncAction } from "@/lib/hooks";

interface SessionInfo {
  id: string;
  ip: string | null;
  userAgent: string | null;
  device: string;
  issuedAt: string | null;
  expiresAt: string | null;
  isCurrent: boolean;
}

function MfaPanel() {
  const { user, api, reloadUser } = useAuth();
  const [secret, setSecret] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [codesModalOpen, setCodesModalOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const genAction = useAsyncAction();
  const toast = useToast();

  const start = async () => {
    setError("");
    try {
      const resp = await api<{ secret: string }>("POST", `/api/v1/users/${user?.id}/mfa/enrol`);
      setSecret(resp.secret);
      setConfirming(true);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.detail : String(exc));
    }
  };

  const confirm = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const code = String(new FormData(e.currentTarget).get("code") ?? "");
    setError("");
    try {
      await api("POST", `/api/v1/users/${user?.id}/mfa/confirm`, { json: { code } });
      setConfirming(false);
      setSecret("");
      await reloadUser();
      toast.success("MFA successfully enabled");
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.detail : String(exc));
    }
  };

  const generateRecoveryCodes = async () => {
    setError("");
    const ok = await genAction.run(async () => {
      const res = await api<{ recoveryCodes: string[] }>("POST", `/api/v1/users/${user?.id}/mfa/generate-recovery-codes`);
      setRecoveryCodes(res.recoveryCodes);
      setCodesModalOpen(true);
      return true;
    });
    if (!ok && genAction.error) {
      setError(genAction.error);
    }
  };

  const copyCodes = () => {
    if (!recoveryCodes.length) return;
    navigator.clipboard.writeText(recoveryCodes.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success("Recovery codes copied to clipboard");
  };

  return (
    <Panel title="Multi-factor authentication">
      <div className="flex flex-col items-start gap-3 p-4">
        <InlineError message={error} />
        {confirming ? (
          <>
            <p className="text-sm">Scan this into your authenticator app, or enter the secret manually:</p>
            <code className="numeric rounded bg-[var(--muted)] px-1.5 py-0.5 text-sm">{secret}</code>
            <form onSubmit={confirm} className="flex items-center gap-2">
              <TextInput name="code" placeholder="6-digit code" maxLength={6} required />
              <ActionButton type="submit">Confirm</ActionButton>
            </form>
          </>
        ) : user?.mfaEnabled ? (
          <div className="flex w-full flex-col gap-3">
            <div className="flex items-center gap-3">
              <Pill tone="success">MFA is active</Pill>
              <span className="text-xs text-[var(--muted-foreground)]">Protected by TOTP authenticator app</span>
            </div>
            <div className="pt-2 border-t border-[var(--border)]">
              <p className="text-xs text-[var(--muted-foreground)] mb-2">
                Emergency recovery codes allow you to access your account if you lose your authenticator device.
              </p>
              <ActionButton size="sm" tone="ghost" onClick={generateRecoveryCodes} loading={genAction.busy}>
                <Key size={14} className="mr-1.5" />
                Generate new recovery codes
              </ActionButton>
            </div>
          </div>
        ) : (
          <ActionButton onClick={start}>Enrol MFA</ActionButton>
        )}

        {/* Recovery codes modal */}
        <Modal open={codesModalOpen} onClose={() => setCodesModalOpen(false)} title="Emergency Recovery Codes">
          <div className="flex flex-col gap-4">
            <div className="rounded bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-400">
              <p className="font-semibold mb-1">Important: Save these codes securely</p>
              <p>Each code can only be used once. If you lose your phone, enter one of these backup codes during sign in.</p>
            </div>

            <div className="grid grid-cols-2 gap-2 rounded bg-[var(--muted)]/50 p-4 font-mono text-sm">
              {recoveryCodes.map((c, i) => (
                <div key={i} className="flex items-center justify-between p-1.5 bg-[var(--card)] rounded border border-[var(--border)]">
                  <span className="text-[var(--foreground)] font-semibold">{c}</span>
                  <span className="text-[10px] text-[var(--muted-foreground)]">#{i + 1}</span>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between pt-2">
              <ActionButton size="sm" tone="ghost" onClick={copyCodes}>
                {copied ? <Check size={14} className="mr-1 text-emerald-500" /> : <Copy size={14} className="mr-1" />}
                {copied ? "Copied" : "Copy all codes"}
              </ActionButton>
              <ActionButton onClick={() => setCodesModalOpen(false)}>Done</ActionButton>
            </div>
          </div>
        </Modal>
      </div>
    </Panel>
  );
}

function PasswordPanel() {
  const { api } = useAuth();
  const [error, setError] = useState("");
  const toast = useToast();

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    setError("");
    const newPassword = String(data.get("newPassword") ?? "");
    if (newPassword !== String(data.get("confirmPassword") ?? "")) {
      setError("New password and confirmation do not match");
      return;
    }
    try {
      await api("POST", "/api/v1/auth/change-password", { json: { currentPassword: String(data.get("currentPassword") ?? ""), newPassword } });
      toast.success("Password successfully changed");
      form.reset();
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.detail : String(exc));
    }
  };

  return (
    <Panel title="Change password">
      <div className="flex flex-col items-start gap-3 p-4">
        <InlineError message={error} />
        <form onSubmit={submit} className="flex w-full max-w-sm flex-col items-start gap-3">
          <Field label="Current password">
            <TextInput name="currentPassword" type="password" required autoComplete="current-password" placeholder="••••••••••••" />
          </Field>
          <Field label="New password">
            <TextInput name="newPassword" type="password" required autoComplete="new-password" placeholder="••••••••••••" />
          </Field>
          <Field label="Confirm new password">
            <TextInput name="confirmPassword" type="password" required autoComplete="new-password" placeholder="••••••••••••" />
          </Field>
          <ActionButton type="submit">Update password</ActionButton>
        </form>
      </div>
    </Panel>
  );
}

function SessionsPanel() {
  const { api } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const query = useApiQuery<{ sessions: SessionInfo[] }>("/api/v1/auth/sessions");
  const sessions = query.data?.sessions ?? [];
  const revokeAction = useAsyncAction();
  const otherSessionsCount = sessions.filter((s) => !s.isCurrent).length;

  const revokeSession = async (id: string) => {
    await revokeAction.run(async () => {
      await api("DELETE", `/api/v1/auth/sessions/${id}`);
      toast.success("Session terminated");
      await qc.invalidateQueries({ queryKey: ["/api/v1/auth/sessions"] });
      return true;
    });
  };

  const revokeOtherSessions = async () => {
    await revokeAction.run(async () => {
      const res = await api<{ revokedCount: number; message: string }>("DELETE", "/api/v1/auth/sessions/other");
      toast.success(res.message);
      await qc.invalidateQueries({ queryKey: ["/api/v1/auth/sessions"] });
      return true;
    });
  };

  return (
    <Panel title="Active devices & sessions">
      <div className="flex flex-col gap-4 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-[var(--muted-foreground)]">
            These devices are currently signed in to your account. Revoking a session immediately logs out that device.
          </p>
          {otherSessionsCount > 0 && (
            <ActionButton size="sm" tone="ghost" onClick={revokeOtherSessions} loading={revokeAction.busy}>
              <LogOut size={14} className="mr-1.5" />
              Sign out of {otherSessionsCount} other device{otherSessionsCount === 1 ? "" : "s"}
            </ActionButton>
          )}
        </div>

        <DataTable columns={["Device / Browser", "IP Address", "Signed In", "Status", ""]} minWidth={540} fit>
          {sessions.map((s) => (
            <tr key={s.id}>
              <td>
                <div className="flex items-center gap-2">
                  <Laptop size={16} className="text-[var(--muted-foreground)] shrink-0" />
                  <span className="font-medium text-[var(--foreground)]">{s.device}</span>
                </div>
              </td>
              <td className="font-mono text-xs text-[var(--muted-foreground)]">{s.ip || "—"}</td>
              <td className="text-xs text-[var(--muted-foreground)]">
                {s.issuedAt ? new Date(s.issuedAt).toLocaleString() : "—"}
              </td>
              <td>
                {s.isCurrent ? <Pill tone="success">This device</Pill> : <Pill>Active</Pill>}
              </td>
              <td className="text-right">
                {!s.isCurrent && (
                  <ActionButton size="sm" tone="ghost" onClick={() => revokeSession(s.id)}>
                    Revoke
                  </ActionButton>
                )}
              </td>
            </tr>
          ))}
        </DataTable>
      </div>
    </Panel>
  );
}

export default function ProfilePage() {
  const { user } = useAuth();
  return (
    <Shell>
      <PageHeader eyebrow="Account" title="Profile & Security" description={user?.email ?? ""} />
      <div className="flex w-full flex-col items-start gap-5">
        <Panel title="Account details">
          <div className="flex flex-wrap items-center gap-6 p-4">
            <div>
              <p className="text-xs text-[var(--muted-foreground)]">Display name</p>
              <p className="font-semibold text-[var(--foreground)]">{user?.displayName || "—"}</p>
            </div>
            <div>
              <p className="text-xs text-[var(--muted-foreground)]">Email address</p>
              <p className="font-semibold text-[var(--foreground)]">{user?.email}</p>
            </div>
            <div>
              <p className="text-xs text-[var(--muted-foreground)]">Roles</p>
              <p className="font-semibold text-[var(--foreground)]">
                {user?.roles?.map((r) => r.name).join(", ") || "No role assigned"}
              </p>
            </div>
          </div>
        </Panel>
        <MfaPanel />
        <PasswordPanel />
        <SessionsPanel />
      </div>
    </Shell>
  );
}
