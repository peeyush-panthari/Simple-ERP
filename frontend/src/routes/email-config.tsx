/**
 * Foundation > Email Config: one outgoing setup per kind of email - purchase orders, logistics quotation requests
 * (RFQ), customer invoices, dispatch notices, user invitations. Each kind can leave from its own mailbox (Gmail, Google
 * Workspace, any SMTP account), with its own sender, Cc/Bcc and on/off switch, and each is saved on its own.
 * Passwords are write-only: the server never sends one back, so the field only says whether one is saved.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { EmailSetupGuide, type GuideTab } from "@/components/erp/email-guide";
import { Shell } from "@/components/erp/shell";
import { ActionButton, Field, Forbidden, InlineError, Note, PageHeader, Pill, SelectInput, TextInput } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { useApiQuery, useAsyncAction } from "@/lib/hooks";

type Security = "none" | "starttls" | "ssl";

interface Purpose {
  key: string;
  label: string;
  description: string;
  configured: boolean;
  sendEnabled: boolean;
  useOwnMailbox: boolean;
  smtpHost: string;
  smtpPort: number;
  security: Security;
  smtpUser: string;
  passwordSet: boolean;
  fromName: string;
  fromEmail: string;
  replyTo: string;
  cc: string[];
  bcc: string[];
  lastTest: { at: string | null; ok: boolean | null; error: string | null };
}

interface Config {
  purposes: Purpose[];
  presets: { key: string; label: string; smtpHost: string; smtpPort: number; security: Security }[];
  environment: { host: string; port: number; security: string; from: string; isLocal: boolean };
}

interface Form {
  sendEnabled: boolean;
  useOwnMailbox: boolean;
  smtpHost: string;
  smtpPort: string;
  security: Security;
  smtpUser: string;
  smtpPassword: string;
  removePassword: boolean;
  fromName: string;
  fromEmail: string;
  replyTo: string;
  cc: string;
  bcc: string;
}

const SECURITY_OPTIONS = [
  { value: "starttls", label: "STARTTLS (port 587) - recommended" },
  { value: "ssl", label: "SSL/TLS (port 465)" },
  { value: "none", label: "None (only for a trusted local relay)" },
];

const splitList = (v: string) => v.split(/[,;\s]+/).map((s) => s.trim()).filter(Boolean);

function toForm(p: Purpose): Form {
  return {
    sendEnabled: p.sendEnabled,
    useOwnMailbox: p.useOwnMailbox,
    smtpHost: p.smtpHost,
    smtpPort: String(p.smtpPort),
    security: p.security,
    smtpUser: p.smtpUser,
    smtpPassword: "",
    removePassword: false,
    fromName: p.fromName,
    fromEmail: p.fromEmail,
    replyTo: p.replyTo,
    cc: p.cc.join(", "),
    bcc: p.bcc.join(", "),
  };
}

function toBody(f: Form) {
  return {
    sendEnabled: f.sendEnabled,
    useOwnMailbox: f.useOwnMailbox,
    smtpHost: f.smtpHost.trim(),
    smtpPort: Number(f.smtpPort) || 0,
    security: f.security,
    smtpUser: f.smtpUser.trim(),
    // null = keep the saved password, "" = remove it, text = replace it
    smtpPassword: f.removePassword ? "" : f.smtpPassword ? f.smtpPassword : null,
    fromName: f.fromName.trim(),
    fromEmail: f.fromEmail.trim(),
    replyTo: f.replyTo.trim() || null,
    cc: splitList(f.cc),
    bcc: splitList(f.bcc),
  };
}

function StatusPill({ p }: { p: Purpose }) {
  if (!p.sendEnabled) return <Pill tone="destructive">Not sent</Pill>;
  if (p.useOwnMailbox) return <Pill tone="success">Own mailbox</Pill>;
  return <Pill tone="muted">Default server</Pill>;
}

function PurposeCard({ purpose, config, others, canWrite, defaultTo, onGuide }: { purpose: Purpose; config: Config; others: Purpose[]; canWrite: boolean; defaultTo: string; onGuide: (t: GuideTab) => void }) {
  const { api } = useAuth();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Form>(() => toForm(purpose));
  const [saved, setSaved] = useState("");
  const [testTo, setTestTo] = useState(defaultTo);
  const [testResult, setTestResult] = useState<{ ok: boolean; error: string | null } | null>(null);
  const [copyFrom, setCopyFrom] = useState("");
  const save = useAsyncAction();
  const test = useAsyncAction();
  const other = useAsyncAction();

  const initial = useMemo(() => JSON.stringify(toForm(purpose)), [purpose]);
  useEffect(() => {
    setForm(toForm(purpose));
  }, [initial]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!testTo && defaultTo) setTestTo(defaultTo);
  }, [defaultTo]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = JSON.stringify(form) !== initial;
  const set = <K extends keyof Form>(k: K, v: Form[K]) => {
    setSaved("");
    setForm((f) => ({ ...f, [k]: v }));
  };
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/email-config"] });
  const url = `/api/v1/email-config/${purpose.key}`;

  const onSave = async () => {
    if (await save.run(() => api<Purpose>("PUT", url, { json: toBody(form) }))) {
      setSaved("Saved.");
      setTestResult(null);
      await refresh();
    }
  };
  const onTest = async () => {
    const out = await test.run(() => api<{ ok: boolean; error: string | null }>("POST", `${url}/test`, { json: { to: testTo.trim() } }));
    if (out) {
      setTestResult(out);
      await refresh();
    }
  };
  const onReset = async () => {
    if (!window.confirm(`Reset "${purpose.label}" to the default? Its own mailbox, Cc/Bcc and switches are removed.`)) return;
    if (await other.run(() => api("DELETE", url))) {
      setSaved("");
      setTestResult(null);
      await refresh();
    }
  };
  const onCopy = async (sourceKey: string) => {
    setCopyFrom("");
    if (sourceKey && (await other.run(() => api("POST", `${url}/copy-from`, { json: { sourceKey } })))) {
      setSaved("Mailbox copied and saved.");
      await refresh();
    }
  };
  const applyPreset = (key: string) => {
    const p = config.presets.find((x) => x.key === key);
    if (p) setForm((f) => ({ ...f, smtpHost: p.smtpHost, smtpPort: String(p.smtpPort), security: p.security }));
  };

  const gmail = /gmail|google/i.test(form.smtpHost);
  const copyable = others.filter((o) => o.key !== purpose.key && o.smtpHost && o.fromEmail);
  const last = purpose.lastTest;
  const summary = !purpose.sendEnabled
    ? "Emails of this kind are not sent."
    : purpose.useOwnMailbox
      ? `Sends from ${purpose.fromName ? `${purpose.fromName} ` : ""}<${purpose.fromEmail}> via ${purpose.smtpHost}`
      : `Sends through the default server (${config.environment.host}).`;

  return (
    <section className="panel w-full">
      <button type="button" className="flex w-full flex-wrap items-center justify-between gap-2 px-4 py-3 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="min-w-0">
          <span className="block text-sm font-semibold">{purpose.label}</span>
          <span className="block text-xs text-[var(--muted-foreground)]">{purpose.description}</span>
          <span className="mt-1 block text-xs">{summary}</span>
        </span>
        <span className="flex items-center gap-2">
          <StatusPill p={purpose} />
          <span className="text-xs text-[var(--primary)]">{open ? "Close" : canWrite ? "Set up" : "View"}</span>
        </span>
      </button>

      {open && (
        <div className="flex flex-col gap-3 border-t border-[var(--border)] px-4 py-4">
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <label className="flex items-center gap-2 text-sm font-medium">
              <input type="checkbox" checked={form.sendEnabled} disabled={!canWrite} onChange={(e) => set("sendEnabled", e.target.checked)} />
              Send these emails
            </label>
            <label className="flex items-center gap-2 text-sm font-medium">
              <input type="checkbox" checked={form.useOwnMailbox} disabled={!canWrite} onChange={(e) => set("useOwnMailbox", e.target.checked)} />
              Use its own mailbox (otherwise the default server)
            </label>
          </div>

          {canWrite && (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Field label="Start from a provider preset">
                <SelectInput value="" onChange={(e) => applyPreset(e.target.value)} placeholder="Fill in the server details…" options={config.presets.map((p) => ({ value: p.key, label: p.label }))} />
              </Field>
              {copyable.length > 0 && (
                <Field label="Or reuse another kind's mailbox" hint="copies its login too">
                  <SelectInput value={copyFrom} onChange={(e) => void onCopy(e.target.value)} placeholder="Copy from…" options={copyable.map((o) => ({ value: o.key, label: `${o.label} (${o.fromEmail})` }))} />
                </Field>
              )}
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div className="md:col-span-2">
              <Field label="SMTP server">
                <TextInput value={form.smtpHost} disabled={!canWrite} placeholder="smtp.gmail.com" onChange={(e) => set("smtpHost", e.target.value)} />
              </Field>
            </div>
            <Field label="Port">
              <TextInput value={form.smtpPort} disabled={!canWrite} inputMode="numeric" onChange={(e) => set("smtpPort", e.target.value.replace(/\D/g, ""))} />
            </Field>
          </div>
          <Field label="Connection security">
            <SelectInput value={form.security} disabled={!canWrite} onChange={(e) => set("security", e.target.value as Security)} options={SECURITY_OPTIONS} />
          </Field>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Field label="Username" hint="usually the full email address">
              <TextInput value={form.smtpUser} disabled={!canWrite} autoComplete="off" placeholder="orders@yourcompany.com" onChange={(e) => set("smtpUser", e.target.value)} />
            </Field>
            <Field label="Password" hint={purpose.passwordSet && !form.removePassword ? "a password is saved" : "not set"}>
              <TextInput
                type="password"
                value={form.smtpPassword}
                disabled={!canWrite || form.removePassword}
                autoComplete="new-password"
                placeholder={purpose.passwordSet ? "•••••••• leave blank to keep it" : "App password"}
                onChange={(e) => set("smtpPassword", e.target.value)}
              />
              {canWrite && purpose.passwordSet && (
                <label className="mt-1 flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
                  <input type="checkbox" checked={form.removePassword} onChange={(e) => set("removePassword", e.target.checked)} /> Remove the saved password
                </label>
              )}
            </Field>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Field label="Sender name" hint="shown to recipients">
              <TextInput value={form.fromName} disabled={!canWrite} placeholder="Yourcompany Purchasing" onChange={(e) => set("fromName", e.target.value)} />
            </Field>
            <Field label="Sender email" hint={gmail ? "must be the Gmail address you log in with" : undefined}>
              <TextInput value={form.fromEmail} disabled={!canWrite} placeholder="orders@yourcompany.com" onChange={(e) => set("fromEmail", e.target.value)} />
            </Field>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <Field label="Reply-to (optional)">
              <TextInput value={form.replyTo} disabled={!canWrite} placeholder="(sender address)" onChange={(e) => set("replyTo", e.target.value)} />
            </Field>
            <Field label="Always Cc" hint="comma-separated">
              <TextInput value={form.cc} disabled={!canWrite} placeholder="accounts@yourcompany.com" onChange={(e) => set("cc", e.target.value)} />
            </Field>
            <Field label="Always Bcc" hint="comma-separated">
              <TextInput value={form.bcc} disabled={!canWrite} placeholder="records@yourcompany.com" onChange={(e) => set("bcc", e.target.value)} />
            </Field>
          </div>

          <p className="text-xs text-[var(--muted-foreground)]">
            Not sure where to find these?{" "}
            <button type="button" className="rx-link" onClick={() => onGuide(gmail ? "gmail" : "other")}>Open the step-by-step setup guide</button>
          </p>

          {gmail && (
            <Note>
              Gmail and Google Workspace need an <b>App password</b>, not your normal password: turn on 2-Step Verification on the Google account, then Google
              Account -&gt; Security -&gt; App passwords. Use <b>smtp.gmail.com</b>, port <b>587</b> with STARTTLS (or 465 with SSL/TLS). Gmail sends from the
              signed-in address, so keep the sender email the same as the username.
            </Note>
          )}

          {canWrite && (
            <div className="flex flex-wrap items-center gap-3">
              <ActionButton onClick={() => void onSave()} loading={save.busy} disabled={!dirty}>{save.busy ? "Saving…" : `Save ${purpose.label.toLowerCase()}`}</ActionButton>
              {purpose.configured && <ActionButton tone="danger" onClick={() => void onReset()} loading={other.busy}>Reset to default</ActionButton>}
              {dirty && !save.busy && <span className="text-xs text-[var(--muted-foreground)]">Unsaved changes.</span>}
              {saved && !dirty && <span className="text-sm text-[var(--success)]">{saved}</span>}
            </div>
          )}
          <InlineError message={save.error || other.error} />

          {canWrite && (
            <div className="flex flex-col gap-2 rounded-md bg-[var(--secondary)] p-3">
              <div className="flex flex-wrap items-end gap-3">
                <div className="min-w-[14rem] flex-1">
                  <Field label="Send a test email to" hint="uses the saved settings above">
                    <TextInput value={testTo} onChange={(e) => setTestTo(e.target.value)} placeholder="you@yourcompany.com" />
                  </Field>
                </div>
                <ActionButton tone="ghost" onClick={() => void onTest()} loading={test.busy} disabled={dirty || !purpose.configured || !testTo.trim()}>
                  {test.busy ? "Sending…" : "Send test email"}
                </ActionButton>
              </div>
              {dirty && <p className="text-xs text-[var(--muted-foreground)]">Save your changes to test them.</p>}
              <InlineError message={test.error} />
              {testResult && (testResult.ok ? <Note>The mail server accepted the test email - check the inbox of {testTo}.</Note> : <InlineError message={`The mail server refused it: ${testResult.error}`} />)}
              {last.at && (
                <p className="flex flex-wrap items-center gap-2 text-xs text-[var(--muted-foreground)]">
                  Last test <Pill tone={last.ok ? "success" : "destructive"}>{last.ok ? "passed" : "failed"}</Pill> on {new Date(last.at).toLocaleString()}
                  {!last.ok && last.error ? ` - ${last.error}` : ""}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function Content() {
  const { can, user } = useAuth();
  const canWrite = can("email_config:write");
  const query = useApiQuery<Config>("/api/v1/email-config");
  const config = query.data;
  const anyOwn = config?.purposes.some((p) => p.useOwnMailbox) ?? false;
  const [guide, setGuide] = useState<GuideTab | null>(null);

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <PageHeader fit eyebrow="Foundation" title="Email Config" description="Choose which mailbox each kind of email is sent from." actions={<ActionButton tone="ghost" onClick={() => setGuide("gmail")}>Setup guide</ActionButton>} />
      <InlineError message={query.error?.message} />
      {config && (
        <Note tone={config.environment.isLocal && !anyOwn ? "warning" : "info"}>
          Every kind can have its own mailbox, sender, Cc/Bcc and on/off switch, saved separately. A kind without its own mailbox goes out through the server&apos;s
          default mail settings ({config.environment.host}:{config.environment.port}
          {config.environment.isLocal ? " - a local test inbox, so nothing reaches real recipients" : ""}).
        </Note>
      )}
      {config?.purposes.map((p) => (
        <PurposeCard key={p.key} purpose={p} config={config} others={config.purposes} canWrite={canWrite} defaultTo={user?.email ?? ""} onGuide={setGuide} />
      ))}
      <EmailSetupGuide open={guide !== null} onClose={() => setGuide(null)} tab={guide ?? "gmail"} onTab={setGuide} />
    </div>
  );
}

export default function EmailConfigPage() {
  const { can } = useAuth();
  return <Shell>{can("email_config:read") ? <Content /> : <Forbidden permission="email_config:read" />}</Shell>;
}
