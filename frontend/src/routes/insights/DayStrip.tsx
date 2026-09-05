/** One portal's last fortnight, one block per day, oldest on the left.
 *
 *  The second chart on this screen, and the one most likely to be read at a
 *  glance rather than studied: green all the way across means the anti-bot
 *  pipeline is getting through, and a red tail means it stopped. Every block
 *  carries the day's counts as its tooltip, because the colour alone cannot say
 *  whether "some failed" was one scan in twenty or nineteen.
 *
 *  A window with no days in it renders as a dash and not as an empty row: a
 *  blank cell where a strip belongs reads as a chart that failed to draw.
 */
import { translateCurrent, useT } from "../../i18n";
import type { ScraperHealthDay } from "../../types";

interface DayCell {
  day: ScraperHealthDay;
  /** The day's verdict, as a background colour. */
  cls: string;
  label: string;
}

export function dayCells(days: ScraperHealthDay[]): DayCell[] {
  return days.map((day) => {
    const failures = day.blocked + day.errors;
    let cls = "bg-positive-dot";
    let state = translateCurrent("health.dayAllOk");
    if (day.attempts === 0) {
      cls = "bg-neutral-dot";
      state = translateCurrent("health.dayNone");
    } else if (failures === day.attempts) {
      cls = "bg-negative-dot";
      state = translateCurrent("health.dayAllFailed");
    } else if (failures > 0) {
      cls = "bg-caution-dot";
      state = translateCurrent("health.daySomeFailed");
    }
    return {
      day,
      cls,
      label: translateCurrent("health.dayLabel", {
        date: day.date,
        state,
        attempts: day.attempts,
        blocked: day.blocked,
        errors: day.errors,
      }),
    };
  });
}

export default function DayStrip({ days }: { days: ScraperHealthDay[] }) {
  const t = useT();
  if (days.length === 0) {
    return <span className="t-dim text-xs">{t("health.noDays")}</span>;
  }

  return (
    <div className="flex items-end gap-[2px]">
      {dayCells(days).map((c) => (
        <span key={c.day.date} title={c.label}
          className={`inline-block w-2.5 h-4 rounded-[3px] ${c.cls}`} />
      ))}
    </div>
  );
}
