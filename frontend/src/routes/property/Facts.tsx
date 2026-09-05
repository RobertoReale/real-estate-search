/** The listing as the ad presents it: the pictures, the price, the facts and
 *  the text somebody wrote to sell it.
 *
 *  This is the left-hand column on a laptop and the top of the sheet on a
 *  phone, and it is deliberately the part with no opinions in it — everything
 *  that judges the price is in the column beside it.
 */
import { useState } from "react";
import { formatNumber, useT } from "../../i18n";
import { formatPrice } from "../../services/api";
import type { Property } from "../../types";
import { Area, Floor, NoImage, Rooms } from "../../ui/icons";
import { humanizeFloor } from "../../utils/format";
import { DealBadge, MarketBadge } from "./Benchmarks";

/** Every photograph the property has, which is one per ad behind it.
 *
 *  A merged property is the same flat advertised twice, and the two agencies
 *  rarely shot the same room — so the second picture is information rather than
 *  decoration. They are all on screen at once rather than behind a carousel: a
 *  gallery of two or three needs no controls, and a control that exists to
 *  reveal one more photo is one more thing to reach with a keyboard.
 *
 *  Portal image URLs are signed and expire, so a dead link is a normal state:
 *  a broken one drops out of the set, and a property whose pictures have all
 *  expired shows the placeholder rather than the browser's torn-page icon. */
function Gallery({ property: p }: { property: Property }) {
  const [broken, setBroken] = useState<string[]>([]);
  const urls = [...new Set([p.image_url, ...p.listings.map((l) => l.image_url)])]
    .filter((url) => url && !broken.includes(url));
  const [hero, ...rest] = urls;

  return (
    <div className="space-y-2">
      <div className="relative aspect-[16/10] rounded-xl overflow-hidden bg-sunken-strong">
        {hero ? (
          <img src={hero} alt={p.title} decoding="async"
            onError={() => setBroken((was) => [...was, hero])}
            className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-ink-faint">
            <NoImage size={64} strokeWidth={1.25} />
          </div>
        )}
      </div>
      {rest.length > 0 && (
        <div className="grid grid-cols-3 gap-2">
          {rest.map((url) => (
            <img key={url} src={url} alt={p.title} loading="lazy" decoding="async"
              onError={() => setBroken((was) => [...was, url])}
              className="aspect-[4/3] w-full rounded-lg object-cover bg-sunken-strong" />
          ))}
        </div>
      )}
    </div>
  );
}

/** A fact slot. Absent when the ad did not say, unlike the card's — nothing
 *  under this is in a grid that a missing line would shift. */
function Fact({ icon, value }: { icon: React.ReactNode; value: string | null }) {
  if (value === null) return null;
  return (
    <span className="self-end inline-flex items-center gap-1">{icon} {value}</span>
  );
}

/** The price, what it comes to per square metre, and where that sits against
 *  the market. */
export function Facts({ property: p }: { property: Property }) {
  const t = useT();
  return (
    <div className="space-y-4">
      <Gallery property={p} />
      <div className="flex flex-wrap items-center gap-4 text-sm">
        <span className="text-2xl font-bold accent-price">
          {formatPrice(p.current_min_price, p.contract)}
        </span>
        {p.sqm && p.current_min_price && (
          <span className="self-end t-muted tnum">
            {t("common.sqmPrice", {
              value: formatNumber(Math.round(p.current_min_price / p.sqm)),
            })}
          </span>
        )}
        <Fact icon={<Rooms />} value={p.rooms ? t("common.rooms", { count: p.rooms }) : null} />
        <Fact icon={<Area />} value={p.sqm ? t("common.sqm", { value: p.sqm.toFixed(0) }) : null} />
        <Fact icon={<Floor />} value={p.floor ? humanizeFloor(p.floor) : null} />
        <DealBadge property={p} />
        <MarketBadge property={p} />
      </div>
    </div>
  );
}

/** The ad's own words, from the first listing that carried any. Scrollable
 *  rather than clamped: an agency description runs to a page and a half, and
 *  the column beside it must not grow to match. */
export function Description({ property: p }: { property: Property }) {
  const t = useT();
  const text = p.listings.find((l) => l.description)?.description;
  if (!text) return null;
  return (
    <section>
      <h3 className="font-semibold mb-2 text-sm uppercase t-muted">
        {t("detail.description")}
      </h3>
      <p className="text-sm t-body whitespace-pre-line max-h-72 overflow-y-auto">{text}</p>
    </section>
  );
}
