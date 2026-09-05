/** One property, in two shapes.
 *
 *  On a laptop it is a page: the grid gives up the screen, and what replaces it
 *  is two columns — the ad on the left (pictures, price, facts, its own words)
 *  and the judgement of it on the right (benchmarks, history, provenance, the
 *  user's notes, the actions). Below `lg` there is no room for two of anything,
 *  so the same blocks arrive as a sheet from the bottom edge with the grid still
 *  behind it.
 *
 *  The two shapes are branched between rather than rendered together and hidden
 *  with CSS: every control here would otherwise exist twice, which is two
 *  entries in the tab order and two of every `data-action` for the inventory to
 *  count. The blocks themselves are built once and placed by the branch, so the
 *  content cannot drift between the shapes.
 */
import { useT } from "../../i18n";
import type { Property, Tag } from "../../types";
import { Chip, IconButton, Sheet } from "../../ui";
import { Close, Disclose, Favorite, Place, Sold } from "../../ui/icons";
import Calculators from "../../components/Calculators";
import { Actions } from "./Actions";
import { Benchmarks } from "./Benchmarks";
import { Description, Facts } from "./Facts";
import { ListingAudit } from "./ListingAudit";
import { Curation } from "./Curation";
import { Provenance } from "./Provenance";
import type { Neighbours } from "./neighbours";

interface Props {
  property: Property;
  /** The page shape, chosen by the caller from the viewport width. */
  page: boolean;
  neighbours: Neighbours;
  /** Go to another property in the set, without leaving this screen. */
  onGo: (id: number) => void;
  onClose: () => void;
  /** The property has left the grid: there is nothing here to stay on. */
  onDeleted: () => void;
  onToggleFavorite: () => void;
  onShowOnMap: (property: Property) => void;
  allTags: Tag[];
  onAddTag: (name: string) => void;
  onRemoveTag: (tagId: number) => void;
  auditEnabled: boolean;
}

export default function PropertyDetail({
  property: p, page, neighbours: near, onGo, onClose, onDeleted, onToggleFavorite,
  onShowOnMap, allTags, onAddTag, onRemoveTag, auditEnabled,
}: Props) {
  const t = useT();

  const title = (
    <>
      {p.contract === "rent" && (
        <Chip tone="rent" size="sm" className="!text-3xs font-bold uppercase align-middle mr-2">
          <Sold /> {t("card.rent")}
        </Chip>
      )}
      {p.title || t("card.untitled")}
    </>
  );
  const where = [p.city, p.zone, p.address].filter(Boolean).join(" · ")
    || t("common.notAvailable");

  /** Moving through the set, and the star. Both shapes carry them; the page puts
   *  them in its header and the sheet above the first block.
   *
   *  The arrows are disabled at the two ends rather than wrapping round: a list
   *  that starts again at the top hides the fact that the user has seen all of
   *  it. They are absent entirely for a property that is in no list — a deep
   *  link the reader's filters exclude — because a control that cannot say what
   *  it would move to is a promise the screen cannot keep. */
  const toolbar = (
    <div className="flex items-center gap-1 shrink-0">
      {near.position !== null && (
        <>
          <IconButton data-action="detail.prev" variant="ghost" size="sm"
            disabled={near.previous === null}
            label={t("detail.previous")}
            onClick={() => near.previous !== null && onGo(near.previous)}>
            <Disclose className="rotate-90" />
          </IconButton>
          <span className="text-xs t-dim tnum whitespace-nowrap">
            {t("detail.position", { position: near.position, total: near.total })}
          </span>
          <IconButton data-action="detail.next" variant="ghost" size="sm"
            disabled={near.next === null}
            label={t("detail.next")}
            onClick={() => near.next !== null && onGo(near.next)}>
            <Disclose className="-rotate-90" />
          </IconButton>
        </>
      )}
      <IconButton data-action="detail.favorite"
        variant="ghost"
        className={p.is_favorite ? "text-favorite-ink" : undefined}
        label={p.is_favorite ? t("card.removeFavorite") : t("card.addFavorite")}
        onClick={onToggleFavorite}>
        <Favorite fill={p.is_favorite ? "currentColor" : "none"} />
      </IconButton>
    </div>
  );

  const ad = (
    <div className="space-y-6">
      <Facts property={p} />
      <Calculators property={p} />
      <Description property={p} />
      <ListingAudit property={p} enabled={auditEnabled} />
    </div>
  );

  const verdict = (
    <div className="space-y-6">
      <Benchmarks property={p} />
      <Provenance property={p} />
      <Curation property={p} allTags={allTags}
        onAddTag={onAddTag} onRemoveTag={onRemoveTag} />
      <Actions property={p} onDone={onDeleted} onShowOnMap={onShowOnMap} />
    </div>
  );

  if (!page) {
    return (
      <Sheet open onOpenChange={(open) => { if (!open) onClose(); }}
        side="bottom" title={title} description={where}
        closeLabel={t("common.close")}>
        <div className="space-y-6">
          <div className="flex justify-end">{toolbar}</div>
          {ad}
          {verdict}
        </div>
      </Sheet>
    );
  }

  // A `div` and not an `article`: the cards are the articles on this screen, and
  // the detail is what one of them opens into rather than another one of them.
  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-xl font-bold">{title}</h2>
          <p className="flex items-center gap-1.5 text-sm t-muted mt-1">
            <Place className="shrink-0" /> {where}
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {toolbar}
          <IconButton data-action="detail.close" variant="ghost"
            label={t("common.close")} onClick={onClose}>
            <Close />
          </IconButton>
        </div>
      </div>

      {/* Wider on the left: the pictures and the description are what needs the
          measure, while the right-hand column is figures and short lines. */}
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        {ad}
        {verdict}
      </div>
    </div>
  );
}
