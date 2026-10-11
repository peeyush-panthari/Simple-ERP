import { TriangleAlert, Sparkles, ArrowLeft } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { Logo } from "@/components/erp/logo";
import { ActionButton, Field, TextInput } from "@/components/erp/ui";
import { ApiError, request } from "@/lib/api";
import { useAuth, type LoginResponse } from "@/lib/auth";

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
    <div className="flex min-h-screen items-center justify-center px-4 py-10" style={{ background: "var(--background)" }}>
      <div className="w-full max-w-sm">
        <div className="mb-7">
          <Logo markClass="h-14 w-auto" textClass="font-display tracking-tight text-[var(--foreground)] font-semibold text-2xl" />
        </div>
        <div className="panel p-6">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--primary)]/10 text-[var(--primary)]">
              <Sparkles size={18} />
            </div>
            <h1 className="text-lg font-semibold text-[var(--foreground)]">Welcome to Axon ERP</h1>
          </div>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            Set up your user account and choose your credentials to get started.
          </p>

          <form onSubmit={submit} className="mt-5 flex flex-col gap-4">
            {!tokenFromUrl && (
              <Field label="Invitation token" hint="Provided in your invitation email">
                <TextInput
                  name="token"
                  required
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="Paste invitation token"
                />
              </Field>
            )}

            <Field label="Full name" hint="Optional, customize your display name">
              <TextInput
                name="displayName"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Jane Doe"
                autoComplete="name"
              />
            </Field>

            <Field label="Password">
              <TextInput
                name="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                autoComplete="new-password"
              />
            </Field>

            <Field label="Confirm password">
              <TextInput
                name="confirmPassword"
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••••••"
                autoComplete="new-password"
              />
            </Field>

            <div className="rounded-md bg-[var(--muted)]/50 p-3 text-[11px] text-[var(--muted-foreground)] space-y-1">
              <p className="font-semibold text-[var(--foreground)]">Password requirements:</p>
              <p>• At least 8 characters long</p>
              <p>• Must include uppercase, lowercase, numbers, and symbols</p>
              <p>• Must not contain your username or email</p>
            </div>

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
      </div>
    </div>
  );
}
