/** Everything that narrows the grid, in a column beside it.
 *
 *  It was a bar across the top, and the shape was the problem rather than the
 *  contents: twenty-odd controls wrapped into four or five rows, and on a
 *  laptop the first property was below the fold on a screen whose whole purpose
 *  is to show properties. A column loses nothing — the controls are narrow and
 *  they stack — and the results start at the top of the page.
 *
 *  **One rendering, two shapes.** Below `lg` the rail is a sheet; from `lg` up
 *  it is inline and collapsible. That choice is made in JavaScript
 *  (`useMediaQuery`) and not in CSS, which is the opposite of what this codebase
 *  does everywhere else, and the reason is that the two shapes are different
 *  markup rather than the same markup styled differently. Rendered both ways
 *  with one hidden, every filter would exist twice: two elements answering to
 *  "City", two entries in the tab order, and two of every `data-action` for the
 *  inventory to trip over. The same argument the shell's navigation makes.
 *
 *  The state that decides which is visible is held here rather than inside the
 *  body, so switching shapes — which a rotation or a resize does — does not
 *  reset the advanced panel a user has just opened.
 */
import { useState } from "react";
import { useT } from "../../i18n";
import { api, authToken, AuthError, fetchExport } from "../../services/api";
import type { PropertyFilters, SearchProfile, Tag } from "../../types";
import { groupSearchProfiles } from "../../utils/searchProfiles";
import { useToasts } from "../../components/Toast";
import { useMediaQuery, DESKTOP_QUERY } from "../../hooks/useMediaQuery";
import { Card, Checkbox, Chip, Field, IconButton, Input, Sheet } from "../../ui";
import { Close, Cog, Disclose, Favorite, Filters, PriceDrop } from "../../ui/icons";
import { activeFilterChips } from "./chips";

interface Props {
  filters: PropertyFilters;
  onChange: (filters: PropertyFilters) => void;
  /** The size of the whole filtered set — what an export would contain. */
  count: number;
  profiles: SearchProfile[];
  tags: Tag[];
}

export default function FilterRail({ filters, onChange, count, profiles, tags }: Props) {
  const t = useT();
  const toasts = useToasts();
  const desktop = useMediaQuery(DESKTOP_QUERY);
  // Two states, not one. The rail starts open on a desktop, where it costs a
  // column that is there anyway, and shut on a phone, where it would cost the
  // whole screen. One shared flag would mean opening the sheet on a phone and
  // then finding the rail collapsed after a rotation.
  const [inlineOpen, setInlineOpen] = useState(true);
  const [sheetOpen, setSheetOpen] = useState(false);
  // only used on the authenticated export path, which is a fetch rather than a
  // navigation and so has a wait the UI has to show
  const [exporting, setExporting] = useState<string | null>(null);
  // Advanced filters live behind a toggle so the common controls stay
  // uncluttered. Opened by default when one is already active (e.g. after a
  // reload), so an applied filter is never hidden.
  const advActiveCount =
    (filters.portal ? 1 : 0) + (filters.agency ? 1 : 0) +
    (filters.deal ? 1 : 0) + (filters.min_sqm_price ? 1 : 0) +
    (filters.max_sqm_price ? 1 : 0) + (filters.merged_only ? 1 : 0);
  const [advOpen, setAdvOpen] = useState(advActiveCount > 0);

  const set = (patch: Partial<PropertyFilters>) => onChange({ ...filters, ...patch });
  const isRent = filters.contract === "rent";
  const activeCount = activeFilterChips(filters, profiles, t).length;
  const open = desktop ? inlineOpen : sheetOpen;

  /** Hand a URL to the browser: opened in a tab for the print-ready PDF report
   *  (which raises the print dialog on load — downloaded, it would print
   *  nothing), saved via a transient anchor for the three file formats. */
  function handOff(url: string, fmt: string, filename?: string) {
    if (fmt === "pdf") {
      window.open(url, "_blank", "noreferrer");
      return;
    }
    const a = document.createElement("a");
    a.href = url;
    a.rel = "noreferrer";
    if (filename) a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function exportAs(fmt: "html" | "markdown" | "csv" | "pdf") {
    const what = filters.only_favorites
      ? t("filters.exportFavorites")
      : isRent
        ? t("filters.exportRentals")
        : t("filters.exportProperties");
    const title = filters.city ? t("filters.exportIn", { what, city: filters.city }) : what;

    // The common case (no API token): let the browser fetch it. Content-
    // Disposition names the file and the PDF prints itself, with no blob in
    // between — the path this has always taken.
    if (!authToken.get()) {
      handOff(api.exportUrl(filters, fmt, title), fmt);
      return;
    }
    // With the token on, that navigation cannot carry the Authorization header
    // and every export came back 401 — the dossier arrived as a page of JSON.
    // Fetch it authenticated instead and hand the browser the result.
    setExporting(fmt);
    try {
      const { blob, filename } = await fetchExport(filters, fmt, title);
      const url = URL.createObjectURL(blob);
      handOff(url, fmt, filename);
      // long enough for the tab/download to have taken it; revoking
      // immediately cancels the transfer in some browsers
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      // an AuthError has already raised the token prompt, and the user has
      // something to do about it on screen; anything else is worth a message,
      // because a button that silently does nothing reads as broken
      if (!(e instanceof AuthError)) {
        toasts.fail(e, { doing: t("toast.exportFailed"), retry: () => exportAs(fmt) });
      }
    } finally {
      setExporting(null);
    }
  }

  const body = (
    <div className="flex flex-col gap-3">
      {/* Free-text search first: it is the fastest way to prune a cluttered
          dashboard ("San Siro", "nuova costruzione") and searches title, zone,
          address and the ad text. */}
      <Field label={t("filters.search")}>
        <div className="relative">
          <Input data-action="filters.query"
            className={filters.q ? "pr-9" : undefined}
            placeholder={t("filters.searchPlaceholder")}
            value={filters.q}
            onChange={(e) => set({ q: e.target.value })}
          />
          {filters.q && (
            <IconButton data-action="filters.query.clear"
              variant="ghost"
              size="sm"
              className="absolute right-2 top-1/2 -translate-y-1/2"
              label={t("filters.clearSearch")}
              onClick={() => set({ q: "" })}>
              <Close size={16} />
            </IconButton>
          )}
        </div>
      </Field>
      {/* Buy/Rent are separate worlds (different price scales, different
          goals), so the toggle is the most prominent control */}
      <div className="flex flex-col gap-1">
        {/* A <label> names a form control; these are button groups, so the name
            goes on a role="group" instead — a <label> with no `for` is
            announced as nothing at all. */}
        <span className="text-xs t-muted">{t("filters.market")}</span>
        <div role="group" aria-label={t("filters.market")}
          className="flex rounded-lg overflow-hidden border border-line-strong">
          <button data-action="filters.contract.sale"
            className={`flex-1 px-3 py-2 text-sm font-medium transition ${
              !isRent
                ? "bg-accent text-on-solid"
                : "bg-control text-ink-dim hover:text-ink-strong"
            }`}
            onClick={() => set({ contract: "sale" })}>
            {t("filters.buy")}
          </button>
          <button data-action="filters.contract.rent"
            className={`flex-1 px-3 py-2 text-sm font-medium transition ${
              isRent
                ? "bg-rent text-on-solid"
                : "bg-control text-ink-dim hover:text-ink-strong"
            }`}
            onClick={() => set({ contract: "rent" })}>
            {t("filters.rent")}
          </button>
        </div>
      </div>
      <Field label={t("filters.city")}>
        <Input data-action="filters.city" placeholder={t("filters.cityPlaceholder")}
          value={filters.city} onChange={(e) => set({ city: e.target.value })} />
      </Field>
      <Field label={t("filters.zone")}>
        <Input data-action="filters.zone" placeholder={t("filters.zonePlaceholder")}
          value={filters.zone} onChange={(e) => set({ zone: e.target.value })} />
      </Field>
      {/* The paired bounds share a row: they are one range asked in two boxes,
          and stacking them made the rail read as four unrelated fields. */}
      <div className="grid grid-cols-2 gap-3">
        <Field label={<>{t("filters.minPrice")} {isRent && t("filters.perMonth")}</>}>
          <Input data-action="filters.minPrice" type="number" placeholder="0"
            value={filters.min_price} onChange={(e) => set({ min_price: e.target.value })} />
        </Field>
        <Field label={<>{t("filters.maxPrice")} {isRent && t("filters.perMonth")}</>}>
          <Input data-action="filters.maxPrice" type="number" placeholder="∞"
            value={filters.max_price} onChange={(e) => set({ max_price: e.target.value })} />
        </Field>
        <Field label={t("filters.minSqm")}>
          <Input data-action="filters.minSqm" type="number" placeholder="0"
            value={filters.min_sqm} onChange={(e) => set({ min_sqm: e.target.value })} />
        </Field>
        <Field label={t("filters.maxSqm")}>
          <Input data-action="filters.maxSqm" type="number" placeholder="∞"
            value={filters.max_sqm} onChange={(e) => set({ max_sqm: e.target.value })} />
        </Field>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-rooms">{t("filters.rooms")}</label>
        <select data-action="filters.rooms" id="filter-rooms" className="input w-full" value={filters.rooms}
          onChange={(e) => set({ rooms: e.target.value })}>
          <option value="">{t("common.all")}</option>
          {[1, 2, 3, 4, 5].map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
      </div>
      {/* Floor bands, parsed server-side from the messy free-text floor label
          ("piano terra", "3", "attico"): a listing whose floor can't be read
          matches no band and drops out while this is set. */}
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-floor">{t("filters.floor")}</label>
        <select data-action="filters.floor" id="filter-floor" className="input w-full" value={filters.floor_band}
          onChange={(e) => set({
            floor_band: e.target.value as PropertyFilters["floor_band"],
          })}>
          <option value="">{t("filters.anyFloor")}</option>
          <option value="ground">{t("filters.floorGround")}</option>
          <option value="low">{t("filters.floorLow")}</option>
          <option value="mid">{t("filters.floorMid")}</option>
          <option value="high">{t("filters.floorHigh")}</option>
          <option value="top">{t("filters.floorTop")}</option>
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-status">{t("filters.status")}</label>
        {/* "gone" = no longer seen by scans for days (inferred exit);
            "sold" = user confirmed the sale; manually hidden/sold properties
            never appear in "All" but each has its own filter here */}
        <select data-action="filters.status" id="filter-status" className="input w-full" value={filters.status}
          onChange={(e) => set({ status: e.target.value })}>
          <option value="active">
            {isRent ? t("filters.statusForRent") : t("filters.statusForSale")}
          </option>
          <option value="filtered">{t("filters.statusFiltered")}</option>
          <option value="gone">{t("filters.statusGone")}</option>
          <option value="sold">
            {isRent ? t("filters.statusRentedOut") : t("filters.statusSold")}
          </option>
          <option value="hidden">{t("filters.statusHidden")}</option>
          <option value="all">{t("filters.statusAll")}</option>
        </select>
      </div>
      {/* Origin: tell inbox imports apart from monitored-search finds — the
          two are otherwise indistinguishable once accepted (source column). */}
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-origin">{t("filters.origin")}</label>
        <select data-action="filters.source" id="filter-origin" className="input w-full" value={filters.source}
          onChange={(e) => set({ source: e.target.value as PropertyFilters["source"] })}>
          <option value="">{t("filters.originAll")}</option>
          <option value="scan">{t("filters.originScan")}</option>
          <option value="email">{t("filters.originEmail")}</option>
        </select>
      </div>
      {tags.length > 0 && (
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted" htmlFor="filter-tag">{t("filters.tag")}</label>
          <select data-action="filters.tag" id="filter-tag" className="input w-full" value={filters.tag}
            onChange={(e) => set({ tag: e.target.value })}>
            <option value="">{t("filters.allTags")}</option>
            {tags.map((tag) => (
              <option key={tag.id} value={tag.name}>{tag.name} ({tag.count})</option>
            ))}
          </select>
        </div>
      )}
      {/* Overlay a saved monitored search on the WHOLE grid (imports included):
          applies its city/contract and its exclusion keywords, so the same
          rules that keep scans clean can prune email imports too. */}
      {profiles.length > 0 && (
        <div className="flex flex-col gap-1">
          {/* This is a FILTER, not a sort: it narrows the grid to the
              properties a saved search actually found (its "Found by"
              provenance), not everything that merely matches its city and
              contract. The label used to read "Match a search", which was
              mistaken for a "best match" ranking. */}
          <label className="text-xs t-muted" htmlFor="filter-profile">{t("filters.limitToSearch")}</label>
          <select data-action="filters.profile" id="filter-profile" className="input w-full" value={filters.profile_id}
            title={t("filters.limitToSearchTitle")}
            onChange={(e) => set({ profile_id: e.target.value })}>
            <option value="">{t("filters.allSearches")}</option>
            {groupSearchProfiles(profiles).map((g) => (
              <option key={g.ids[0]} value={String(g.ids[0])}>
                {g.baseName} {g.portals.length > 1 ? `(${g.portals.join("/")})` : ""}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="flex flex-col gap-1">
        <Checkbox data-action="filters.priceDrops"
          checked={filters.only_price_drops}
          onCheckedChange={(v) => set({ only_price_drops: v === true })}
          label={<span className="flex items-center gap-1.5"><PriceDrop /> {t("filters.priceDrops")}</span>} />
        <Checkbox data-action="filters.favorites"
          checked={filters.only_favorites}
          onCheckedChange={(v) => set({ only_favorites: v === true })}
          label={<span className="flex items-center gap-1.5"><Favorite /> {t("filters.favorites")}</span>} />
      </div>

      {/* Gateway to the advanced filters — kept below the common ones so the
          rail stays short. The badge shows how many advanced filters are active
          even while the panel is collapsed. */}
      <div className="border-t border-line pt-3">
        <button data-action="filters.advanced.toggle" type="button"
          className="flex w-full items-center gap-1.5 text-sm accent-link hover:underline"
          aria-expanded={advOpen}
          onClick={() => setAdvOpen((o) => !o)}>
          <Cog /> {t("filters.more")}
          {advActiveCount > 0 && (
            <Chip tone="accent" className="!px-1.5 !rounded-pill font-semibold">
              {advActiveCount}
            </Chip>
          )}
          <Disclose className={`ml-auto t-dim transition-transform ${advOpen ? "rotate-180" : ""}`} />
        </button>
      </div>

      {advOpen && (
        <div className="p-3 rounded-xl panel flex flex-col gap-3 animate-fade-in">
          <p className="text-xs font-medium t-muted">
            {t("filters.moreTitle")}{" "}
            <span className="font-normal t-dim">{t("filters.moreHint")}</span>
          </p>
          {/* Portal: a card can group ads from several portals, so this keeps
              the ones present on the chosen portal (see main.py `portal=`). */}
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted" htmlFor="filter-portal">{t("filters.portal")}</label>
            <select data-action="filters.portal" id="filter-portal" className="input w-full" value={filters.portal}
              onChange={(e) => set({
                portal: e.target.value as PropertyFilters["portal"],
              })}>
              <option value="">{t("filters.anyPortal")}</option>
              <option value="immobiliare">Immobiliare</option>
              <option value="idealista">Idealista</option>
            </select>
          </div>
          <Field label={t("filters.agency")}>
            <Input data-action="filters.agency" placeholder={t("filters.agencyPlaceholder")}
              value={filters.agency} onChange={(e) => set({ agency: e.target.value })} />
          </Field>
          {/* Deal quality reads the Deal Score (€/sqm gap vs the local median).
              "Fair or better" drops the overpriced; both need a local median,
              so unscored cards fall out when set. */}
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted" htmlFor="filter-deal">{t("filters.deal")}</label>
            <select data-action="filters.deal" id="filter-deal" className="input w-full" value={filters.deal}
              onChange={(e) => set({
                deal: e.target.value as PropertyFilters["deal"],
              })}>
              <option value="">{t("filters.anyDeal")}</option>
              <option value="undervalued">{t("filters.dealUndervalued")}</option>
              <option value="fair_plus">{t("filters.dealFairPlus")}</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t("filters.minSqmPrice")}>
              <Input data-action="filters.minSqmPrice" type="number" placeholder="0"
                value={filters.min_sqm_price}
                onChange={(e) => set({ min_sqm_price: e.target.value })} />
            </Field>
            <Field label={t("filters.maxSqmPrice")}>
              <Input data-action="filters.maxSqmPrice" type="number" placeholder="∞"
                value={filters.max_sqm_price}
                onChange={(e) => set({ max_sqm_price: e.target.value })} />
            </Field>
          </div>
          <Checkbox data-action="filters.mergedOnly"
            className="min-h-11 sm:min-h-0"
            checked={filters.merged_only}
            onCheckedChange={(v) => set({ merged_only: v === true })}
            label={t("filters.mergedOnly")} />
        </div>
      )}

      {/* Export the filtered set as a shareable offline file (no server, no
          DB) — see services/exporter.py. It belongs to the rail rather than to
          the result header because what it exports *is* the query: change a
          filter and the same four buttons produce a different file. */}
      <div className="flex flex-col gap-1 border-t border-line pt-3">
        <span className="text-xs t-muted">{t("filters.export")} {count > 0 && `(${count})`}</span>
        <div role="group" aria-label={t("filters.export")}
          className="flex rounded-lg overflow-hidden border border-line-strong">
          {/* The action id is carried in the tuple rather than built from
              `fmt`: the inventory is checked against the literal strings in
              the source, and a template one would be invisible to it. */}
          {([
            ["html", "HTML", "export.html"],
            ["markdown", "MD", "export.markdown"],
            ["csv", "CSV", "export.csv"],
            ["pdf", "PDF", "export.pdf"],
          ] as const).map(
            ([fmt, label, action]) => (
              <button key={fmt} data-action={action}
                className="flex-1 px-3 py-2 text-sm font-medium transition
                  bg-control text-ink-dim hover:text-ink-strong
                  disabled:opacity-40 disabled:cursor-not-allowed"
                disabled={count === 0 || exporting !== null}
                title={
                  fmt === "pdf"
                    ? t("filters.exportPdfTitle", { count })
                    : t("filters.exportTitle", { count, format: label })
                }
                onClick={() => exportAs(fmt)}>
                {exporting === fmt ? "…" : label}
              </button>
            ),
          )}
        </div>
      </div>
    </div>
  );

  const toggle = (
    <button data-action="filters.toggle" type="button"
      className="flex w-full items-center gap-2 rounded-lg border border-line-strong
        bg-control px-3 py-2 text-sm font-medium text-ink-strong transition
        hover:border-accent-line btn-focus"
      aria-expanded={open}
      title={open ? t("filters.hide") : t("filters.show")}
      onClick={() => (desktop ? setInlineOpen((o) => !o) : setSheetOpen(true))}>
      <Filters /> {t("filters.title")}
      {activeCount > 0 && (
        <Chip tone="accent" className="!px-1.5 !rounded-pill font-semibold">
          {activeCount}
        </Chip>
      )}
      <Disclose className={`ml-auto t-dim transition-transform ${open ? "rotate-180" : ""}`} />
    </button>
  );

  // `aria-label` rather than a visible heading: the toggle already names the
  // region in words, and a second copy of "Filters" above it would be read out
  // twice and take a line the rail cannot spare on a phone.
  return (
    <aside aria-label={t("filters.title")}
      className={desktop && inlineOpen ? "lg:w-72 lg:shrink-0" : undefined}>
      {toggle}
      {desktop
        ? inlineOpen && <Card className="mt-3">{body}</Card>
        : (
          <Sheet open={sheetOpen} onOpenChange={setSheetOpen}
            side="bottom"
            title={t("filters.title")}
            description={t("filters.railHint")}
            closeLabel={t("common.close")}>
            {body}
          </Sheet>
        )}
    </aside>
  );
}
