/** What an optional model read in the ad's own text.
 *
 *  Off by default and never automatic: the GET below reads a stored row and
 *  nothing else, so opening a property cannot spend a model request — only the
 *  button underneath can. It sits directly beneath the description because what
 *  it is about is that description, and a reading printed far from the text it
 *  read is a claim with nothing to check it against.
 */
import { formatDate, useT } from "../../i18n";
import { useAuditProperty, useListingAudit } from "../../queries/properties";
import type { Property } from "../../types";
import { Button } from "../../ui";
import { Describe, Warning } from "../../ui/icons";
import { useToasts } from "../../components/Toast";

/** The auditor answers inside a fixed vocabulary (backend `listing_auditor`),
 *  so each value has a translation rather than being printed raw. */
const CONDITION_KEYS = {
  new: "audit.conditionNew",
  renovated: "audit.conditionRenovated",
  good: "audit.conditionGood",
  to_renovate: "audit.conditionToRenovate",
  unknown: "audit.conditionUnknown",
} as const;

const TENANT_KEYS = {
  yes: "audit.tenantYes",
  no: "audit.tenantNo",
  unknown: "audit.tenantUnknown",
} as const;

/** One group of the audit's findings; absent entirely when the ad said nothing
 *  about it, since an empty heading reads as a missing answer. */
function AuditList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <p className="text-xs font-medium">{title}</p>
      <ul className="list-disc list-inside t-body text-xs space-y-0.5">
        {items.map((item, i) => <li key={i}>{item}</li>)}
      </ul>
    </div>
  );
}

interface Props {
  property: Property;
  /** Whether the optional listing auditor is switched on in Settings. Off is
   *  the default, and then nothing here renders at all — a button for a feature
   *  that would answer "turn it on first" is not a feature. */
  enabled: boolean;
}

export function ListingAudit({ property: p, enabled }: Props) {
  const t = useT();
  const toasts = useToasts();
  const hasDescription = p.listings.some((l) => l.description);
  const audit = useListingAudit(p.id, enabled).data ?? null;
  const readAudit = useAuditProperty();

  async function readListing(force: boolean) {
    try {
      await readAudit.mutateAsync({ id: p.id, force });
    } catch (e) {
      toasts.fail(e, { doing: t("audit.failed"), retry: () => readListing(force) });
    }
  }

  if (!enabled || !hasDescription) return null;

  return (
    <section>
      <h3 className="flex items-center gap-1.5 font-semibold mb-2 text-sm uppercase t-muted">
        <Describe /> {t("audit.title")}
      </h3>
      {audit && (
        <div className="rounded-xl panel p-3 text-sm space-y-2">
          {audit.stale && (
            <p className="flex items-start gap-1.5 text-xs accent-bad">
              <Warning className="shrink-0 mt-0.5" /> {t("audit.stale")}
            </p>
          )}
          {audit.summary && <p className="t-body">{audit.summary}</p>}
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
            <span>
              <span className="t-dim">{t("audit.condition")}: </span>
              {t(CONDITION_KEYS[audit.condition])}
            </span>
            <span>
              <span className="t-dim">{t("audit.tenant")}: </span>
              {t(TENANT_KEYS[audit.tenant])}
            </span>
          </div>
          <AuditList title={t("audit.costs")} items={audit.costs} />
          <AuditList title={t("audit.concerns")} items={audit.concerns} />
          <AuditList title={t("audit.negotiation")} items={audit.negotiation} />
          <p className="text-2xs t-dim">
            {t("audit.footer", { model: audit.model, date: formatDate(audit.created_at) })}
            {" · "}
            {t("audit.disclaimer")}
          </p>
        </div>
      )}
      <div className="mt-2">
        <Button data-action="detail.audit.read"
          size="sm"
          disabled={readAudit.isPending}
          onClick={() => readListing(audit !== null)}
          title={t("audit.buttonTitle")}>
          {readAudit.isPending
            ? t("audit.reading")
            : audit
              ? t("audit.again")
              : <><Describe /> {t("audit.button")}</>}
        </Button>
      </div>
    </section>
  );
}
