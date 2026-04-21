import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ThemeToggle } from "./ThemeToggle";
import { useSettingsStore } from "@/stores/useSettingsStore";

describe("ThemeToggle", () => {
  beforeEach(() => {
    useSettingsStore.setState({ theme: "light" });
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  it("renders with light theme icon", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button");
    expect(button).toHaveAttribute("aria-label", expect.stringContaining("light"));
  });

  it("cycles through themes on click", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button");

    // light -> dark
    fireEvent.click(button);
    expect(useSettingsStore.getState().theme).toBe("dark");

    // dark -> system
    fireEvent.click(button);
    expect(useSettingsStore.getState().theme).toBe("system");

    // system -> light
    fireEvent.click(button);
    expect(useSettingsStore.getState().theme).toBe("light");
  });

  it("persists theme to localStorage", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button");

    fireEvent.click(button);
    expect(localStorage.getItem("tokenlens-theme")).toBe("dark");
  });

  it("applies dark class to document when dark theme", () => {
    useSettingsStore.setState({ theme: "dark" });
    render(<ThemeToggle />);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("removes dark class when light theme", () => {
    document.documentElement.classList.add("dark");
    useSettingsStore.setState({ theme: "light" });
    render(<ThemeToggle />);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
