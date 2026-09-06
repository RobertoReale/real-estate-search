/** A search's health, as one element.
 *
 *  The state is the chip; the run's own words appear only under a state that is
 *  asking for something. That asymmetry is the point rather than an oversight.
 *  "18 listings, 2 new" under a search that is working is a fact nobody acts on,
 *  and printing it on every row is what turned this column into prose in the
 *  first place — whereas "the portal answered 403" under a blocked one is the
 *  *reason*, and an alarm with no reason attached is worse than no alarm.
 *
 *  See `health.ts` for which state wins over which, and why a search that finds
 *  nothing is not a search that is broken.
 */

import { useT } from "../../i18n";
import { Chip } from "../../ui";
import { needsAttention, profileHealth, type HealthInput } from "./health";

interface Props {
  profile: HealthInput;
  /** `sm` for the per-portal lines inside a merged row, where the state is a
   *  detail of a line that already has one. */
  size?: "sm" | "md";
  /** Off for those same per-portal lines: the row's own health element is
   *  directly above them and already carries the reason, and saying it twice on
   *  one row is the duplication this component exists to end. */
  reason?: boolean;
  className?: string;
}

export default function ProfileHealth({
  profile, size = "md", reason: withReason = true, className,
}: Props) {
  const t = useT();
  const health = profileHealth(profile);
  const reason = withReason && needsAttention(health.state) ? health.detail : "";

  return (
    <div className={`flex min-w-0 flex-col items-start gap-1 ${className ?? ""}`}>
      <Chip tone={health.tone} size={size} dot>
        {t(health.label)}
        {/* One failure is an incident and every scan has them; a streak is a
            pattern, and it is the second number that decides whether the user
            goes and looks. Invariant 11 alerts on the same threshold. */}
        {health.streak > 1 && <span className="tabular-nums">×{health.streak}</span>}
      </Chip>
      {reason && (
        <p className="text-2xs t-dim max-w-[13rem] break-words">{reason}</p>
      )}
    </div>
  );
}
