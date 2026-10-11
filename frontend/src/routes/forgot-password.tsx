import { CheckCircle2, TriangleAlert, ArrowLeft } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { Logo } from "@/components/erp/logo";
import { ActionButton, Field, TextInput } from "@/components/erp/ui";
import { ApiError, request } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function ForgotPasswordPage() {
  const { status } = useAuth();
  const [email, setEmail] = useState("");
  const [tenantSlug, setTenantSlug] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (status === "authenticated") return <Navigate to="/" replace />;

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await request("POST", "/api/v1/auth/forgot-password", {
        json: {
          email,
          ...(tenantSlug ? { tenantSlug } : {}),
        },
      });
      setSubmitted(true);
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.detail : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10" style={{ background: "var(--background)" }}>
      <div className="w-full max-w-sm">
        <div className="mb-7">
          <Logo markClass="h-14 w-auto" textClass="font-display tracking-tight text-[var(--foreground)] font-semibold text-2xl" />
        </div>
        <div className="panel p-6">
          {submitted ? (
            <div className="flex flex-col items-center text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 size={28} />
              </div>
              <h1 className="mt-4 text-lg font-semibold text-[var(--foreground)]">Check your inbox</h1>
              <p className="mt-2 text-sm text-[var(--muted-foreground)]">
                If an account with <strong className="text-[var(--foreground)]">{email}</strong> exists, we have sent instructions to reset your password.
              </p>
              <p className="mt-4 text-xs text-[var(--muted-foreground)]">
                Didn't receive an email? Check your spam folder or contact your system administrator.
              </p>
              <div className="mt-6 flex w-full flex-col gap-2">
                <ActionButton tone="ghost" className="w-full justify-center" onClick={() => setSubmitted(false)}>
                  Send another request
                </ActionButton>
                <Link to="/login" className="flex items-center justify-center gap-1.5 text-xs text-[var(--primary)] hover:underline pt-2">
                  <ArrowLeft size={14} /> Back to sign in
                </Link>
              </div>
            </div>
          ) : (
            <>
              <h1 className="text-lg font-semibold text-[var(--foreground)]">Reset password</h1>
              <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                Enter your work email address and we'll send you a link to reset your credentials.
              </p>
              <form onSubmit={submit} className="mt-5 flex flex-col gap-4">
                <Field label="Email address">
                  <TextInput
                    name="email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    autoComplete="email"
                  />
                </Field>
                <Field label="Organization / Tenant slug" hint="Optional, leave blank for default">
                  <TextInput
                    name="tenantSlug"
                    value={tenantSlug}
                    onChange={(e) => setTenantSlug(e.target.value)}
                    placeholder="e.g. axon-main"
                  />
                </Field>
                {error && (
                  <div className="inline-error" role="alert">
                    <TriangleAlert size={16} className="mt-0.5 shrink-0" />
                    <p>{error}</p>
                  </div>
                )}
                <ActionButton type="submit" loading={busy} className="w-full justify-center">
                  {busy ? "Sending link…" : "Send reset link"}
                </ActionButton>
                <div className="pt-2 text-center">
                  <Link to="/login" className="inline-flex items-center gap-1.5 text-xs text-[var(--primary)] hover:underline">
                    <ArrowLeft size={14} /> Back to sign in
                  </Link>
                </div>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
