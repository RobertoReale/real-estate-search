/** The way back into the capability setup, and the honest list of what is still
 *  switched off.
 *
 *  The wizard runs once on a fresh install and then never asks again, which is
 *  right — being walked through a form every Monday is worse than the form. But
 *  "never asks again" and "cannot be answered later" are different things, and
 *  only the first one is wanted: a user who skipped Telegram in March has no way
 *  of knowing in April that they skipped it. So this sits at the top of the
 *  dialog, names the capabilities that are still off, and opens the same five
 *  screens.
 *
 *  It lists what is *off*, not what is unfinished. Skipping every step is a
 *  complete answer, and a dialog that keeps a red count against a decision the
 *  user already made is nagging rather than informing — `pendingGroups` reads
 *  the settings themselves, so a capability configured by hand in this dialog
 *  drops off the list without the wizard being involved.
 */
import { useNavigate } from "react-router-dom";

import { useT } from "../../i18n";
import { groupTitleKey, pendingGroups } from "../../routes/setup";
import { SETUP } from "../../routes/params";
import type { Settings } from "../../types";
import { Button, Chip } from "../../ui";
import { Cog } from "../../ui/icons";
import { SectionHeading } from "./controls";

export function SetupSection({ settings }: { settings: Settings }) {
  const t = useT();
  const navigate = useNavigate();
  const pending = pendingGroups(settings);

  return (
    <>
      <SectionHeading first icon={Cog}>{t("setup.section.title")}</SectionHeading>
      <p className="text-sm t-muted mb-3">
        {pending.length > 0 ? t("setup.section.pending") : t("setup.section.allOn")}
      </p>
      {pending.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {pending.map((id) => <Chip key={id} tone="neutral">{t(groupTitleKey(id))}</Chip>)}
        </div>
      )}
      <Button data-action="settings.setup.open" onClick={() => void navigate(SETUP)}>
        {settings.setup_completed ? t("setup.section.reopen") : t("setup.section.open")}
      </Button>
    </>
  );
}
