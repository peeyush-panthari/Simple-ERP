import { HelpCircle, TriangleAlert } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate, useLocation, Link, type Location } from "react-router-dom";
import { Logo } from "@/components/erp/logo";
import { ActionButton, Field, TextInput } from "@/components/erp/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { status, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mfaRequired, setMfaRequired] = useState(false);
  const [useRecoveryCode, setUseRecoveryCode] = useState(false);
  const [error, setError] = useState("");
  const [lockedUntil, setLockedUntil] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const fromState = (location.state as { from?: Location })?.from;
  const targetPath = fromState?.pathname
    ? `${fromState.pathname}${fromState.search || ""}${fromState.hash || ""}`
    : "/";

  if (status === "authenticated") return <Navigate to={targetPath} replace />;

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    setLockedUntil(null);
    try {
      const result = await login({
        email: String(form.get("email") ?? ""),
        password: String(form.get("password") ?? ""),
        mfaCode: mfaRequired && !useRecoveryCode ? (String(form.get("mfaCode") ?? "").trim() || undefined) : undefined,
        mfaRecoveryCode: mfaRequired && useRecoveryCode ? (String(form.get("mfaRecoveryCode") ?? "").trim() || undefined) : undefined,
      });
      if (result.mfaRequired) setMfaRequired(true);
      else navigate(targetPath, { replace: true });
    } catch (exc) {
      if (exc instanceof ApiError) {
        setError(exc.detail);
        const locked = (exc.body?.meta as any)?.lockedUntil || (exc.body as any)?.lockedUntil;
        if (locked || exc.code === "ACCOUNT_LOCKED") {
          setLockedUntil(locked ? String(locked) : "locked");
        }
      } else {
        setError("Something went wrong");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <main id="main-content" role="main" aria-label="Sign in" className="flex min-h-screen items-center justify-center px-4 py-10" style={{ background: "var(--background)" }}>
      <div className="w-full max-w-sm">
        <div className="mb-7">
          <Logo markClass="h-14 w-auto" textClass="font-display tracking-tight text-[var(--foreground)] font-semibold text-2xl" />
        </div>
        <div className="panel p-6">
          <h1 className="text-lg font-semibold text-[var(--foreground)]">Sign in</h1>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">Your role determines which modules and actions are available.</p>
          <form onSubmit={submit} className="mt-5 flex flex-col gap-4">
            <Field label="Email" htmlFor="login-email">
              <TextInput id="login-email" name="email" type="email" required placeholder="you@company.com" autoComplete="username" />
            </Field>
            <Field label="Password" htmlFor="login-password">
              <TextInput id="login-password" name="password" type="password" required placeholder="••••••••••••" autoComplete="current-password" />
            </Field>
            <div className="-mt-2 text-right">
              <Link to="/forgot-password" className="text-xs text-[var(--primary)] hover:underline">
                Forgot password?
              </Link>
            </div>
            {mfaRequired && (
              <>
                {!useRecoveryCode ? (
                  <Field label="Authentication code" hint="From your authenticator app" htmlFor="login-mfa-code">
                    <TextInput id="login-mfa-code" name="mfaCode" maxLength={6} required placeholder="000000" className="numeric tracking-[0.3em]" />
                  </Field>
                ) : (
                  <Field label="Emergency recovery code" hint="e.g. ABCD-EFGH" htmlFor="login-recovery-code">
                    <TextInput id="login-recovery-code" name="mfaRecoveryCode" required placeholder="XXXX-XXXX" className="uppercase font-mono" />
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
            {lockedUntil && (
              <div className="panel p-3 border-[var(--destructive)] text-xs text-[var(--destructive)]">
                <p className="font-semibold">Security Alert: Account Temporarily Locked</p>
                <p className="mt-1">
                  {lockedUntil !== "locked"
                    ? `Too many failed attempts. Account is locked until ${new Date(lockedUntil).toLocaleTimeString()}. Please wait or contact your administrator.`
                    : "Too many failed attempts. Account is temporarily locked. Please contact your administrator."}
                </p>
              </div>
            )}
            <ActionButton type="submit" loading={busy} disabled={Boolean(lockedUntil)} className="w-full justify-center">
              {busy ? "Signing in…" : "Sign in"}
            </ActionButton>
          </form>
        </div>
        <p className="mt-4 text-center text-[11px] text-[var(--muted-foreground)]">Sessions use short-lived access tokens with rotating refresh tokens.</p>
        <div className="mt-3 flex justify-center">
          <button
            type="button"
            aria-label="Help and training documentation"
            onClick={() => navigate("/training")}
            className="inline-flex items-center gap-1.5 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            <HelpCircle className="w-3.5 h-3.5" /> Help &amp; Interactive Training
          </button>
        </div>
      </div>
    </main>
  );
}
