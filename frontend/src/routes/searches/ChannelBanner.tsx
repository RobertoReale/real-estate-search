/** One banner, for the whole account, when the alerts have nowhere to go.
 *
 *  Whether Telegram has a token is a fact about the account, not about a search,
 *  and it used to be printed inside the list — once per row to begin with, three
 *  identical paragraphs down a list of three searches, which reads as three
 *  problems; then once per distinct unconfigured channel, which is better and
 *  still two banners for one thing to go and fix.
 *
 *  It is one line now, at the top of the page, above the list it is not part of.
 *  The two rules it keeps from the version it replaces are the ones worth
 *  keeping: it names the channel that is actually missing rather than the
 *  general idea of notifications, and it stays silent about a channel no search
 *  has asked for — an account that only ever wanted Telegram is not misconfigured
 *  for having no SMTP host.
 *
 *  It ends in the link, because a warning whose remedy is somewhere else is a
 *  warning the reader has to go and find.
 */

import { NavLink } from "react-router-dom";

import { useT } from "../../i18n";
import type { SearchProfile, Settings } from "../../types";
import { channelReadiness } from "../../components/searchProfiles/helpers";
import { Card } from "../../ui";
import { Cog, Warning } from "../../ui/icons";
import { SETTINGS } from "../params";

interface Props {
  profiles: SearchProfile[];
  settings: Settings | null;
}

/** Which channels the saved searches actually ask for and cannot get. `""` is
 *  "wherever the account sends things", so it is unmet only when *neither*
 *  route works; `"none"` is a choice and never unmet (invariant 21). */
export function unmetChannels(
  profiles: SearchProfile[], settings: Settings | null,
): Set<"telegram" | "email"> {
  const ready = channelReadiness(settings);
  const unmet = new Set<"telegram" | "email">();
  for (const p of profiles) {
    switch (p.notify_channels || "") {
      case "none":
        break;
      case "telegram":
        if (!ready.telegram) unmet.add("telegram");
        break;
      case "email":
        if (!ready.email) unmet.add("email");
        break;
      default:
        // "any channel": one working route is enough, and when there is none
        // the honest complaint is about both rather than about a favourite.
        if (!ready.telegram && !ready.email) {
          unmet.add("telegram");
          unmet.add("email");
        }
    }
  }
  return unmet;
}

export default function ChannelBanner({ profiles, settings }: Props) {
  const t = useT();
  const unmet = unmetChannels(profiles, settings);
  if (unmet.size === 0) return null;

  const message = unmet.size > 1
    ? t("profiles.channelsNone")
    : unmet.has("telegram")
      ? t("profiles.channelsTelegram")
      : t("profiles.channelsEmail");

  return (
    <Card asChild padding="md"
      className="border-caution-line bg-caution-tint">
      {/* `alert` and not `status`: it is rendered on arrival rather than in
          response to anything, so there is nothing for a polite region to
          interrupt, and a user who reaches this page by keyboard should meet it
          before the list. */}
      <section role="alert" aria-labelledby="channel-banner">
        <p id="channel-banner"
          className="flex flex-wrap items-center gap-x-1.5 gap-y-2 text-sm text-caution-ink-strong">
          <Warning className="shrink-0" />
          {message}{" "}
          <NavLink data-action="notify.toSettings" to={SETTINGS}
            className="inline-flex items-center gap-1 font-medium text-accent-link underline underline-offset-2">
            <Cog /> {t("profiles.channelsFix")}
          </NavLink>
        </p>
      </section>
    </Card>
  );
}
