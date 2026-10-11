import { TriangleAlert } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate, Link } from "react-router-dom";
import { Logo } from "@/components/erp/logo";
import { ActionButton, Field, TextInput } from "@/components/erp/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { status, login } = useAuth();
  const navigate = useNavigate();
  const [mfaRequired, setMfaRequired] = useState(false);
  const [useRecoveryCode, setUseRecoveryCode] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (status === "authenticated") return <Navigate to="/" replace />;

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const result = await login({
        email: String(form.get("email") ?? ""),
        password: String(form.get("password") ?? ""),
        mfaCode: useRecoveryCode ? undefined : String(form.get("mfaCode") ?? ""),
        mfaRecoveryCode: useRecoveryCode ? String(form.get("mfaRecoveryCode") ?? "") : undefined,
      });
      if (result.mfaRequired) setMfaRequired(true);
      else navigate("/", { replace: true });
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.detail : "Something went wrong");
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
          <h1 className="text-lg font-semibold text-[var(--foreground)]">Sign in</h1>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">Your role determines which modules and actions are available.</p>
          <form onSubmit={submit} className="mt-5 flex flex-col gap-4">
            <Field label="Email">
              <TextInput name="email" type="email" required placeholder="you@company.com" autoComplete="username" />
            </Field>
            <Field label="Password">
              <TextInput name="password" type="password" required placeholder="••••••••••••" autoComplete="current-password" />
            </Field>
            <div className="-mt-2 text-right">
              <Link to="/forgot-password" className="text-xs text-[var(--primary)] hover:underline">
                Forgot password?
              </Link>
            </div>
            {mfaRequired && (
              <>
                {!useRecoveryCode ? (
                  <Field label="Authentication code" hint="From your authenticator app">
                    <TextInput name="mfaCode" maxLength={6} required placeholder="000000" className="numeric tracking-[0.3em]" />
                  </Field>
                ) : (
                  <Field label="Emergency recovery code" hint="e.g. ABCD-EFGH">
                    <TextInput name="mfaRecoveryCode" required placeholder="XXXX-XXXX" className="uppercase font-mono" />
                  </Field>
                )}
                <div className="-mt-2 text-right">
                  <button
                    type="button"
                    onClick={() => setUseRecoveryCode(!useRecoveryCode)}
                    className="text-xs text-[var(--primary)] hover:underline"
                  >
                    {useRecoveryCode ? "Use authenticator app code" : "Lost phone? Use recovery code"}
                  </button>
                </div>
              </>
            )}
            {error && (
              <div className="inline-error" role="alert">
                <TriangleAlert size={16} className="mt-0.5 shrink-0" />
                <p>{error}</p>
              </div>
            )}
            <ActionButton type="submit" loading={busy} className="w-full justify-center">
              {busy ? "Signing in…" : "Sign in"}
            </ActionButton>
          </form>
        </div>
        <p className="mt-4 text-center text-[11px] text-[var(--muted-foreground)]">Sessions use short-lived access tokens with rotating refresh tokens.</p>
      </div>
    </div>
  );
}
