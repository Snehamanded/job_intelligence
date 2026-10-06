import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AuthForm } from "@/components/auth/auth-form";

describe("login form validation", () => {
  it("shows errors and does not submit when fields are empty", async () => {
    const onSubmit = vi.fn();
    render(<AuthForm mode="login" onSubmit={onSubmit} />);

    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("rejects a malformed email", async () => {
    const onSubmit = vi.fn();
    render(<AuthForm mode="login" onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText("Email"), "not-an-email");
    await userEvent.type(screen.getByLabelText("Password"), "secret-pass");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits trimmed credentials when valid", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<AuthForm mode="login" onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText("Email"), "  sneha@example.com ");
    await userEvent.type(screen.getByLabelText("Password"), "secret-pass");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(onSubmit).toHaveBeenCalledWith({ email: "sneha@example.com", password: "secret-pass" });
  });

  it("shows the server error passed in", () => {
    render(<AuthForm mode="login" onSubmit={vi.fn()} error="Invalid email or password" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Invalid email or password");
  });
});

describe("register form validation", () => {
  it("requires a long enough, confirmed password", async () => {
    const onSubmit = vi.fn();
    render(<AuthForm mode="register" onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText("Email"), "sneha@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "short");
    await userEvent.type(screen.getByLabelText("Confirm password"), "different");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Use at least 8 characters.")).toBeInTheDocument();
    expect(screen.getByText("Passwords do not match.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
