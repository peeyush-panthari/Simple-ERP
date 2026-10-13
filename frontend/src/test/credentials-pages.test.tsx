import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import ForgotPasswordPage from "@/routes/forgot-password";
import ResetPasswordPage from "@/routes/reset-password";
import AcceptInvitePage from "@/routes/accept-invite";
import * as api from "@/lib/api";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    status: "anonymous",
    login: vi.fn(),
    setSession: vi.fn(),
    logout: vi.fn(),
    can: () => true,
    canAny: () => true,
  }),
}));

describe("Credentials & User Lifecycle Pages", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe("ForgotPasswordPage", () => {
    it("renders email input and handles submission successfully", async () => {
      const postSpy = vi.spyOn(api, "request").mockResolvedValueOnce({
        message: "If an account with that email exists, a password reset email has been sent.",
      });

      render(
        <MemoryRouter>
          <ForgotPasswordPage />
        </MemoryRouter>
      );

      expect(screen.getByText("Reset password")).toBeInTheDocument();
      const emailInput = screen.getByPlaceholderText("you@company.com");
      fireEvent.change(emailInput, { target: { value: "user@example.com" } });

      const submitButton = screen.getByRole("button", { name: "Send reset link" });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith("POST", "/api/v1/auth/forgot-password", {
          json: { email: "user@example.com" },
        });
      });

      await waitFor(() => {
        expect(screen.getByText("Check your inbox")).toBeInTheDocument();
      });
    });
  });

  describe("ResetPasswordPage", () => {
    it("validates that passwords match before sending request", async () => {
      const postSpy = vi.spyOn(api, "request");

      render(
        <MemoryRouter initialEntries={["/reset-password?token=sample-token"]}>
          <ResetPasswordPage />
        </MemoryRouter>
      );

      const passwordInputs = screen.getAllByPlaceholderText("••••••••••••");
      fireEvent.change(passwordInputs[0], { target: { value: "Secret#123" } });
      fireEvent.change(passwordInputs[1], { target: { value: "Different#456" } });

      const submitButton = screen.getByRole("button", { name: "Reset password" });
      fireEvent.click(submitButton);

      expect(screen.getByText("Passwords do not match")).toBeInTheDocument();
      expect(postSpy).not.toHaveBeenCalled();
    });

    it("submits password reset successfully with URL token", async () => {
      const postSpy = vi.spyOn(api, "request").mockResolvedValueOnce({
        message: "Password has been successfully reset. You may now sign in.",
      });

      render(
        <MemoryRouter initialEntries={["/reset-password?token=valid-token-123"]}>
          <ResetPasswordPage />
        </MemoryRouter>
      );

      const passwordInputs = screen.getAllByPlaceholderText("••••••••••••");
      fireEvent.change(passwordInputs[0], { target: { value: "NewSecure#Pass123" } });
      fireEvent.change(passwordInputs[1], { target: { value: "NewSecure#Pass123" } });

      const submitButton = screen.getByRole("button", { name: "Reset password" });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith("POST", "/api/v1/auth/reset-password", {
          json: { token: "valid-token-123", newPassword: "NewSecure#Pass123" },
        });
      });

      await waitFor(() => {
        expect(screen.getByText("Password reset")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Proceed to sign in" })).toBeInTheDocument();
      });
    });
  });

  describe("AcceptInvitePage", () => {
    it("submits accepted invitation with display name and logs in", async () => {
      const postSpy = vi.spyOn(api, "request").mockResolvedValueOnce({
        accessToken: "access-token-xyz",
        refreshToken: "refresh-token-xyz",
        user: { id: "user-1", email: "new@example.com", displayName: "Jane Doe", roles: [] },
      });

      render(
        <MemoryRouter initialEntries={["/accept-invite?token=invite-token-abc"]}>
          <AcceptInvitePage />
        </MemoryRouter>
      );

      expect(screen.getByText("Welcome to Simple ERP")).toBeInTheDocument();

      const nameInput = screen.getByPlaceholderText("Jane Doe");
      fireEvent.change(nameInput, { target: { value: "Jane Doe" } });

      const passwordInputs = screen.getAllByPlaceholderText("••••••••••••");
      fireEvent.change(passwordInputs[0], { target: { value: "Welcome#2026Secure" } });
      fireEvent.change(passwordInputs[1], { target: { value: "Welcome#2026Secure" } });

      const submitButton = screen.getByRole("button", { name: "Activate account & sign in" });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(postSpy).toHaveBeenCalledWith("POST", "/api/v1/auth/accept-invite", {
          json: {
            token: "invite-token-abc",
            password: "Welcome#2026Secure",
            displayName: "Jane Doe",
          },
        });
      });
    });
  });
});
