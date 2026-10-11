import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LoginPage from "@/routes/login";
import ProfilePage from "@/routes/profile";
import * as authModule from "@/lib/auth";
import { ToastProvider } from "@/components/erp/extras";

describe("Phase 3 - Sessions & MFA Recovery Codes", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe("LoginPage - Emergency Recovery Codes", () => {
    it("allows user to toggle to recovery code when MFA is required and submits correctly", async () => {
      const mockLogin = vi.fn();
      mockLogin
        .mockResolvedValueOnce({ mfaRequired: true }) // first submit prompts MFA
        .mockResolvedValueOnce({ mfaRequired: false, accessToken: "tok", refreshToken: "ref" }); // second submit succeeds

      vi.spyOn(authModule, "useAuth").mockReturnValue({
        status: "anonymous",
        user: null,
        login: mockLogin,
        api: vi.fn(),
        logout: vi.fn(),
        can: () => true,
        canAny: () => true,
        reloadUser: vi.fn(),
        setSession: vi.fn(),
      } as unknown as ReturnType<typeof authModule.useAuth>);

      render(
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      );

      const emailInput = screen.getByPlaceholderText("you@company.com");
      const passwordInput = screen.getByPlaceholderText("••••••••••••");
      fireEvent.change(emailInput, { target: { value: "alice@example.com" } });
      fireEvent.change(passwordInput, { target: { value: "Secret#123" } });

      const submitBtn = screen.getByRole("button", { name: "Sign in" });
      fireEvent.click(submitBtn);

      // Should now see MFA prompt
      await waitFor(() => {
        expect(screen.getByPlaceholderText("000000")).toBeInTheDocument();
        expect(screen.getByText("Lost phone? Use recovery code")).toBeInTheDocument();
      });

      // Toggle to emergency recovery code
      const toggleLink = screen.getByText("Lost phone? Use recovery code");
      fireEvent.click(toggleLink);

      await waitFor(() => {
        expect(screen.getByPlaceholderText("XXXX-XXXX")).toBeInTheDocument();
        expect(screen.queryByPlaceholderText("000000")).not.toBeInTheDocument();
        expect(screen.getByText("Use authenticator app code")).toBeInTheDocument();
      });

      // Fill recovery code and submit
      const recoveryInput = screen.getByPlaceholderText("XXXX-XXXX");
      fireEvent.change(recoveryInput, { target: { value: "ABCD-1234" } });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith({
          email: "alice@example.com",
          password: "Secret#123",
          mfaCode: undefined,
          mfaRecoveryCode: "ABCD-1234",
        });
      });
    });
  });

  describe("ProfilePage - Sessions & Recovery Codes", () => {
    it("renders active sessions, allows revoking single session and other sessions", async () => {
      const mockApi = vi.fn().mockImplementation((method: string, path: string) => {
        if (method === "GET" && path === "/api/v1/auth/sessions") {
          return Promise.resolve({
            sessions: [
              {
                id: "sess-1",
                device: "Chrome on macOS",
                ip: "192.168.1.1",
                issuedAt: "2026-10-11T12:00:00Z",
                isCurrent: true,
              },
              {
                id: "sess-2",
                device: "Safari on iPhone",
                ip: "192.168.1.2",
                issuedAt: "2026-10-10T10:00:00Z",
                isCurrent: false,
              },
            ],
          });
        }
        if (method === "DELETE" && path === "/api/v1/auth/sessions/sess-2") {
          return Promise.resolve({ message: "Session terminated" });
        }
        if (method === "DELETE" && path === "/api/v1/auth/sessions/other") {
          return Promise.resolve({ revokedCount: 1, message: "1 other session revoked" });
        }
        return Promise.resolve({});
      });

      vi.spyOn(authModule, "useAuth").mockReturnValue({
        status: "authenticated",
        user: {
          id: "u123",
          email: "admin@example.com",
          displayName: "Admin User",
          roles: [{ name: "Administrator" }],
          permissions: ["*"],
          mfaEnabled: true,
        },
        permissions: ["*"],
        login: vi.fn(),
        api: mockApi,
        logout: vi.fn(),
        can: () => true,
        canAny: () => true,
        reloadUser: vi.fn(),
        setSession: vi.fn(),
      } as unknown as ReturnType<typeof authModule.useAuth>);

      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <ToastProvider>
              <ProfilePage />
            </ToastProvider>
          </MemoryRouter>
        </QueryClientProvider>
      );

      // Verify sessions display
      await waitFor(() => {
        expect(screen.getByText("Chrome on macOS")).toBeInTheDocument();
        expect(screen.getByText("Safari on iPhone")).toBeInTheDocument();
        expect(screen.getByText("This device")).toBeInTheDocument();
        expect(screen.getByText("Sign out of 1 other device")).toBeInTheDocument();
      });

      // Revoke specific session
      const revokeBtn = screen.getByRole("button", { name: "Revoke" });
      fireEvent.click(revokeBtn);

      await waitFor(() => {
        expect(mockApi).toHaveBeenCalledWith("DELETE", "/api/v1/auth/sessions/sess-2");
      });

      // Revoke all other sessions
      const revokeOtherBtn = screen.getByRole("button", { name: "Sign out of 1 other device" });
      fireEvent.click(revokeOtherBtn);

      await waitFor(() => {
        expect(mockApi).toHaveBeenCalledWith("DELETE", "/api/v1/auth/sessions/other");
      });
    });

    it("generates and displays MFA recovery codes in modal", async () => {
      const generatedCodes = [
        "A1B2-C3D4",
        "E5F6-G7H8",
        "J9K0-L1M2",
        "N3P4-Q5R6",
        "S7T8-U9V0",
        "W1X2-Y3Z4",
        "2B3C-4D5F",
        "6G7H-8J9K",
      ];

      const mockApi = vi.fn().mockImplementation((method: string, path: string) => {
        if (method === "GET" && path === "/api/v1/auth/sessions") {
          return Promise.resolve({ sessions: [] });
        }
        if (method === "POST" && path === "/api/v1/users/u123/mfa/generate-recovery-codes") {
          return Promise.resolve({ recoveryCodes: generatedCodes });
        }
        return Promise.resolve({});
      });

      const writeTextMock = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, {
        clipboard: {
          writeText: writeTextMock,
        },
      });

      vi.spyOn(authModule, "useAuth").mockReturnValue({
        status: "authenticated",
        user: {
          id: "u123",
          email: "admin@example.com",
          displayName: "Admin User",
          roles: [{ name: "Administrator" }],
          permissions: ["*"],
          mfaEnabled: true,
        },
        permissions: ["*"],
        login: vi.fn(),
        api: mockApi,
        logout: vi.fn(),
        can: () => true,
        canAny: () => true,
        reloadUser: vi.fn(),
        setSession: vi.fn(),
      } as unknown as ReturnType<typeof authModule.useAuth>);

      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <ToastProvider>
              <ProfilePage />
            </ToastProvider>
          </MemoryRouter>
        </QueryClientProvider>
      );

      const generateBtn = screen.getByRole("button", { name: /generate new recovery codes/i });
      fireEvent.click(generateBtn);

      await waitFor(() => {
        expect(mockApi).toHaveBeenCalledWith("POST", "/api/v1/users/u123/mfa/generate-recovery-codes");
        expect(screen.getByText("Emergency Recovery Codes")).toBeInTheDocument();
        expect(screen.getByText("A1B2-C3D4")).toBeInTheDocument();
        expect(screen.getByText("6G7H-8J9K")).toBeInTheDocument();
      });

      // Test clipboard copy
      const copyBtn = screen.getByRole("button", { name: /copy all codes/i });
      fireEvent.click(copyBtn);

      await waitFor(() => {
        expect(writeTextMock).toHaveBeenCalledWith(generatedCodes.join("\n"));
      });
    });
  });
});
