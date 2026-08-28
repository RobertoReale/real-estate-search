/** What the settings dialog does when the backend does not answer.
 *
 * The dialog cannot render a field until `getSettings` resolves, so the failure
 * path is the whole test: it used to leave `settings` null for ever, which
 * rendered nothing at all — the gear button looked broken, there was no close
 * button to press, and the rejection was unhandled. A dialog that reports the
 * failure and offers a retry is the fix; this pins it, because the regression
 * is invisible until the backend is actually down.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsModal from "./SettingsModal";
import { api } from "../services/api";

describe("SettingsModal when the settings cannot be loaded", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the error and a way out instead of rendering nothing", async () => {
    vi.spyOn(api, "getSettings").mockRejectedValue(new Error("Connection refused"));
    const onClose = vi.fn();

    render(<SettingsModal onClose={onClose} />);

    // the message names the underlying failure rather than swallowing it
    const status = await screen.findByRole("status");
    expect(status.textContent).toContain("Connection refused");

    // and the dialog is dismissable, which the blank render never was
    expect(screen.getAllByRole("button", { name: /close|chiudi/i }).length)
      .toBeGreaterThan(0);
  });

  it("retries the load, and shows the form once the backend answers", async () => {
    const settings = { excluded_keywords: [] } as unknown as Awaited<
      ReturnType<typeof api.getSettings>
    >;
    const getSettings = vi.spyOn(api, "getSettings")
      .mockRejectedValueOnce(new Error("Connection refused"))
      .mockResolvedValueOnce(settings);

    render(<SettingsModal onClose={vi.fn()} />);
    (await screen.findByRole("button", { name: /try again|riprova/i })).click();

    await waitFor(() => expect(getSettings).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /try again|riprova/i })).toBeNull(),
    );
  });
});
