import { ArrowLeft, CheckCircle2, HelpCircle, Sparkles, TriangleAlert } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { Logo } from "@/components/erp/logo";
import { ActionButton, Field, TextInput } from "@/components/erp/ui";
import { ApiError, request } from "@/lib/api";
import { useAuth, type LoginResponse } from "@/lib/auth";
import { cn } from "@/lib/utils";

export default function AcceptInvitePage() {
  const { status, setSession } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const tokenFromUrl = params.get("token") ?? "";

  const [token, setToken] = useState(tokenFromUrl);
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (status === "authenticated") return <Navigate to="/" replace />;

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (!token.trim()) {
      setError("Invitation token is required");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const resp = await request<LoginResponse>("POST", "/api/v1/auth/accept-invite", {
        json: {
          token: token.trim(),
          password,
          ...(displayName.trim() ? { displayName: displayName.trim() } : {}),
        },
      });
      setSession(resp);
      navigate("/", { replace: true });
    } catch (exc) {
      if (exc instanceof ApiError) {
        if (exc.code === "INVALID_INVITE_TOKEN") {
          setError("The invitation token is invalid or has expired. Ask your administrator to resend your invite.");
        } else {
          setError(exc.detail);
        }
      } else {
        setError("An error occurred while accepting your invitation. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <main id="main-content" role="main" aria-label="Accept invitation" className="flex min-h-screen items-center justify-center px-4 py-10" style={{ background: "var(--background)" }}>
      <div className="w-full max-w-sm">
        <div className="mb-7">
          <Logo markClass="h-14 w-auto" textClass="font-display tracking-tight text-[var(--foreground)] font-semibold text-2xl" />
        </div>
        <div className="panel p-6">
          <nav aria-label="breadcrumb" className="breadcrumb mb-4 flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
            <Link to="/login" className="hover:text-[var(--foreground)]">Sign In</Link>
            <span>/</span>
            <span className="font-medium text-[var(--foreground)]">Accept Invitation</span>
          </nav>
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--primary)]/10 text-[var(--primary)]">
              <Sparkles size={18} />
            </div>
            <h1 className="text-lg font-semibold text-[var(--foreground)]">Welcome to Simple ERP</h1>
          </div>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            Set up your user account and choose your credentials to get started.
          </p>

          <form onSubmit={submit} className="mt-5 flex flex-col gap-4">
            {!tokenFromUrl && (
              <Field label="Invitation token" hint="Provided in your invitation email" htmlFor="invite-token">
                <TextInput
                  id="invite-token"
                  name="token"
                  required
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="Paste invitation token"
                />
              </Field>
            )}

            <Field label="Full name" hint="Optional, customize your display name" htmlFor="invite-display-name">
              <TextInput
                id="invite-display-name"
                name="displayName"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Jane Doe"
                autoComplete="name"
              />
            </Field>

            <Field label="Password" htmlFor="invite-password">
              <TextInput
                id="invite-password"
                name="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                autoComplete="new-password"
              />
            </Field>

            <Field label="Confirm password" htmlFor="invite-confirm-password">
              <TextInput
                id="invite-confirm-password"
                name="confirmPassword"
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••••••"
                autoComplete="new-password"
              />
            </Field>

            {(() => {
              const hasMinLength = password.length >= 8;
              const hasUpper = /[A-Z]/.test(password);
              const hasNumber = /[0-9]/.test(password);
              const hasSymbol = /[^A-Za-z0-9]/.test(password);
              const passwordsMatch = confirmPassword.length > 0 && password === confirmPassword;

              return (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 text-xs space-y-2">
                  <p className="font-semibold text-[var(--foreground)] text-[11px] uppercase tracking-wider">Password Requirements</p>
                  <div className="grid grid-cols-2 gap-1.5 text-[11px]">
                    <div className={cn("flex items-center gap-1.5", hasMinLength ? "text-emerald-600 dark:text-emerald-400 font-medium" : "text-[var(--muted-foreground)]")}>
                      <CheckCircle2 size={13} className={hasMinLength ? "text-emerald-600 dark:text-emerald-400" : "opacity-30"} />
                      <span>8+ characters</span>
                    </div>
                    <div className={cn("flex items-center gap-1.5", hasUpper ? "text-emerald-600 dark:text-emerald-400 font-medium" : "text-[var(--muted-foreground)]")}>
                      <CheckCircle2 size={13} className={hasUpper ? "text-emerald-600 dark:text-emerald-400" : "opacity-30"} />
                      <span>1+ uppercase letter</span>
                    </div>
                    <div className={cn("flex items-center gap-1.5", hasNumber ? "text-emerald-600 dark:text-emerald-400 font-medium" : "text-[var(--muted-foreground)]")}>
                      <CheckCircle2 size={13} className={hasNumber ? "text-emerald-600 dark:text-emerald-400" : "opacity-30"} />
                      <span>1+ number</span>
                    </div>
                    <div className={cn("flex items-center gap-1.5", hasSymbol ? "text-emerald-600 dark:text-emerald-400 font-medium" : "text-[var(--muted-foreground)]")}>
                      <CheckCircle2 size={13} className={hasSymbol ? "text-emerald-600 dark:text-emerald-400" : "opacity-30"} />
                      <span>1+ special symbol</span>
                    </div>
                  </div>
                  {confirmPassword.length > 0 && (
                    <div className={cn("pt-1.5 border-t border-[var(--border)] flex items-center gap-1.5 text-[11px]", passwordsMatch ? "text-emerald-600 dark:text-emerald-400 font-medium" : "text-amber-600 dark:text-amber-400")}>
                      <CheckCircle2 size={13} className={passwordsMatch ? "text-emerald-600 dark:text-emerald-400" : "opacity-30"} />
                      <span>{passwordsMatch ? "Passwords match ✓" : "Passwords do not match yet"}</span>
                    </div>
                  )}
                </div>
              );
            })()}

            {error && (
              <div className="inline-error" role="alert">
                <TriangleAlert size={16} className="mt-0.5 shrink-0" />
                <p>{error}</p>
              </div>
            )}

            <ActionButton type="submit" loading={busy} className="w-full justify-center">
              {busy ? "Activating account…" : "Activate account & sign in"}
            </ActionButton>

            <div className="pt-2 text-center">
              <Link to="/login" className="inline-flex items-center gap-1.5 text-xs text-[var(--primary)] hover:underline">
                <ArrowLeft size={14} /> Back to sign in
              </Link>
            </div>
          </form>
        </div>
        <div className="mt-4 flex justify-center">
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
