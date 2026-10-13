import { ArrowLeft, CheckCircle2, HelpCircle, KeyRound, TriangleAlert } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { Logo } from "@/components/erp/logo";
import { ActionButton, Field, TextInput } from "@/components/erp/ui";
import { ApiError, request } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

export default function ResetPasswordPage() {
  const { status } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const tokenFromUrl = params.get("token") ?? "";

  const [token, setToken] = useState(tokenFromUrl);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (status === "authenticated") return <Navigate to="/" replace />;

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (!token.trim()) {
      setError("Password reset token is required");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await request("POST", "/api/v1/auth/reset-password", {
        json: {
          token: token.trim(),
          newPassword,
        },
      });
      setSuccess(true);
    } catch (exc) {
      if (exc instanceof ApiError) {
        if (exc.code === "INVALID_RESET_TOKEN") {
          setError("The password reset token is invalid or has expired. Please request a new one.");
        } else if (exc.code === "PASSWORD_REUSED") {
          setError(exc.detail || "You cannot reuse any of your recent passwords.");
        } else {
          setError(exc.detail);
        }
      } else {
        setError("An error occurred while resetting your password. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <main id="main-content" role="main" aria-label="Reset password" className="flex min-h-screen items-center justify-center px-4 py-10" style={{ background: "var(--background)" }}>
      <div className="w-full max-w-sm">
        <div className="mb-7">
          <Logo markClass="h-14 w-auto" textClass="font-display tracking-tight text-[var(--foreground)] font-semibold text-2xl" />
        </div>
        <div className="panel p-6">
          <nav aria-label="breadcrumb" className="breadcrumb mb-4 flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
            <Link to="/login" className="hover:text-[var(--foreground)]">Sign In</Link>
            <span>/</span>
            <span className="font-medium text-[var(--foreground)]">Set New Password</span>
          </nav>
          {success ? (
            <div className="flex flex-col items-center text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 size={28} />
              </div>
              <h1 className="mt-4 text-lg font-semibold text-[var(--foreground)]">Password reset</h1>
              <p className="mt-2 text-sm text-[var(--muted-foreground)]">
                Your password has been changed successfully. You may now sign in using your new credentials.
              </p>
              <div className="mt-6 w-full">
                <Link to="/login">
                  <ActionButton className="w-full justify-center">
                    Proceed to sign in
                  </ActionButton>
                </Link>
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--primary)]/10 text-[var(--primary)]">
                  <KeyRound size={18} />
                </div>
                <h1 className="text-lg font-semibold text-[var(--foreground)]">Set new password</h1>
              </div>
              <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                Choose a strong password meeting the organization's security policy.
              </p>

              <form onSubmit={submit} className="mt-5 flex flex-col gap-4">
                {!tokenFromUrl && (
                  <Field label="Reset token" hint="Paste the token from your email" htmlFor="reset-token">
                    <TextInput
                      id="reset-token"
                      name="token"
                      required
                      value={token}
                      onChange={(e) => setToken(e.target.value)}
                      placeholder="e.g. z8Uu-cdIb5SYMUvtiZ6td..."
                    />
                  </Field>
                )}

                <Field label="New password" htmlFor="reset-new-password">
                  <TextInput
                    id="reset-new-password"
                    name="newPassword"
                    type="password"
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="••••••••••••"
                    autoComplete="new-password"
                  />
                </Field>

                <Field label="Confirm new password" htmlFor="reset-confirm-password">
                  <TextInput
                    id="reset-confirm-password"
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
                  const hasMinLength = newPassword.length >= 8;
                  const hasUpper = /[A-Z]/.test(newPassword);
                  const hasNumber = /[0-9]/.test(newPassword);
                  const hasSymbol = /[^A-Za-z0-9]/.test(newPassword);
                  const passwordsMatch = confirmPassword.length > 0 && newPassword === confirmPassword;

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
                  {busy ? "Updating password…" : "Reset password"}
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
