/** Which channels the banner is entitled to complain about.
 *
 *  The rule it must not lose: it stays silent about a channel no search has
 *  asked for. An account that only ever wanted Telegram is not misconfigured for
 *  having no SMTP host, and a warning about a route nobody selected is the kind
 *  a reader learns to scroll past — taking the real one with it.
 */

import { describe, expect, it } from "vitest";

import { unmetChannels } from "./ChannelBanner";
import type { SearchProfile, Settings } from "../../types";

function search(notify_channels: string): SearchProfile {
  return { notify_channels } as SearchProfile;
}

const NOTHING = {} as Settings;
const TELEGRAM_READY = {
  telegram_enabled: true, telegram_token_set: true, telegram_chat_id: "42",
} as Settings;
const EMAIL_READY = {
  email_enabled: true, smtp_host: "smtp.example", email_to: "a@example",
} as Settings;

describe("unmetChannels", () => {
  it("says nothing at all with no searches saved", () => {
    expect([...unmetChannels([], NOTHING)]).toEqual([]);
  });

  it("names both when a search wants any channel and there is none", () => {
    expect([...unmetChannels([search("")], NOTHING)].sort())
      .toEqual(["email", "telegram"]);
  });

  it("is satisfied by one working route when the search asked for any", () => {
    expect([...unmetChannels([search("")], TELEGRAM_READY)]).toEqual([]);
    expect([...unmetChannels([search("")], EMAIL_READY)]).toEqual([]);
  });

  it("names only the channel a search actually chose", () => {
    expect([...unmetChannels([search("telegram")], EMAIL_READY)]).toEqual(["telegram"]);
    expect([...unmetChannels([search("email")], TELEGRAM_READY)]).toEqual(["email"]);
  });

  it("keeps quiet about a silenced search", () => {
    // Invariant 21: silence is a choice, and a search that asked for no alerts
    // is not a search whose alerts are broken.
    expect([...unmetChannels([search("none")], NOTHING)]).toEqual([]);
  });

  it("reports one problem however many searches inherit it", () => {
    const three = [search("telegram"), search("telegram"), search("telegram")];
    expect([...unmetChannels(three, EMAIL_READY)]).toEqual(["telegram"]);
  });

  it("counts an enabled channel with no credentials as missing", () => {
    // Mirrors notifier.py's own gating: enabling Telegram without a token is a
    // delivery route that silently drops messages, and the UI must not claim it.
    const halfSet = { telegram_enabled: true, telegram_token_set: false } as Settings;
    expect([...unmetChannels([search("telegram")], halfSet)]).toEqual(["telegram"]);
  });
});
