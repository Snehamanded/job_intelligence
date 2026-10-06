import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PreferencesForm } from "@/components/profile/preferences-form";
import type { Preferences } from "@/lib/api/client";

const initial: Preferences = {
  target_roles: [],
  remote_scope: "none",
  onsite_locations: [],
  open_to: ["full_time"],
  min_salary: null,
  currency: null,
  salary_unknown_policy: "include",
};

describe("PreferencesForm", () => {
  it("requires a currency with a minimum salary and at least one employment type", async () => {
    const onSubmit = vi.fn();
    render(<PreferencesForm initial={initial} onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText("Minimum annual salary"), "1200000");
    await userEvent.click(screen.getByLabelText("Full-time"));
    await userEvent.click(screen.getByRole("button", { name: "Save preferences" }));

    expect(
      await screen.findByText("Choose a currency for the minimum salary."),
    ).toBeInTheDocument();
    expect(screen.getByText("Choose at least one employment type.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("rejects a non-numeric salary", async () => {
    const onSubmit = vi.fn();
    render(<PreferencesForm initial={initial} onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("Minimum annual salary"), "12 LPA");
    await userEvent.click(screen.getByRole("button", { name: "Save preferences" }));
    expect(await screen.findByText(/whole number/)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits preferences in the API shape", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<PreferencesForm initial={initial} onSubmit={onSubmit} />);

    await userEvent.type(
      screen.getByLabelText("Target roles"),
      "Backend Engineer, Python Developer, ",
    );
    await userEvent.click(screen.getByLabelText("Remote within India"));
    await userEvent.type(screen.getByLabelText(/Cities/), "Bangalore, Hyderabad");
    await userEvent.click(screen.getByLabelText("Contract"));
    await userEvent.type(screen.getByLabelText("Minimum annual salary"), "1200000");
    await userEvent.type(screen.getByLabelText("Currency"), "inr");
    await userEvent.click(screen.getByLabelText("Hide them"));
    await userEvent.click(screen.getByRole("button", { name: "Save preferences" }));

    expect(onSubmit).toHaveBeenCalledWith({
      target_roles: ["Backend Engineer", "Python Developer"],
      remote_scope: "india",
      onsite_locations: ["Bangalore", "Hyderabad"],
      open_to: ["full_time", "contract"],
      min_salary: 1200000,
      currency: "INR",
      salary_unknown_policy: "exclude",
    });
  });
});
