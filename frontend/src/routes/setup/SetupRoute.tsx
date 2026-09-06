/** The capability setup: five screens between a first search and one that works.
 *
 *  The guided first run gets a user to a saved search. That search then meets a
 *  portal that answers 403, or collects perfectly and tells nobody, and both are
 *  a settings dialog away — a dialog with eight sections, fifty-four fields and
 *  no opinion about which of them matters today. This walks the same fields in
 *  the order they pay off, five questions long, and every one of them optional.
 *
 *  Three things it deliberately does not do:
 *
 *  **It does not require anything.** "Skip for now" is on every step and is a
 *  real control beside the other one, not small type under it. Skipping all five
 *  lands on the listings with an app that works exactly as it did before, which
 *  is what "off by default" already meant.
 *
 *  **It does not ask what the backend can see.** Whether the harvester imports,
 *  whether Camoufox is installed, whether a cookie is stored — all of it arrives
 *  with the settings, so a field the machine cannot honour is not offered and
 *  the first step opens by saying what it found. `groups.ts` holds that rule.
 *
 *  **It does not post what it was given.** `GET /api/settings` masks a secret to
 *  `"***"`; a form that posts its whole model back would write those three
 *  characters over a working key, and the field would still say "saved". Each
 *  step posts only its own fields, and a secret box left empty is not posted at
 *  all — see `payloadFor`, and the backend test that guards the round trip.
 *
 *  It is a route rather than a dialog for the same reason the guide is: the
 *  address can be returned to, the navigation stays reachable, and being half
 *  way through is a state the app can be left in.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  fieldHintKey, fieldLabelKey, fieldsFor, GROUPS, groupAt, groupBodyKey, groupTitleKey,
  optionLabelKey, optionsFor, payloadFor, seed,
  type SetupField, type SetupGroup, type SetupValues,
} from "./groups";
import { SecretStatus } from "../../components/settings/controls";
import { useToasts } from "../../components/Toast";
import { useT, type TFunction } from "../../i18n";
import { useSaveSettings, useSettingsForm } from "../../queries/settings";
import type { Settings } from "../../types";
import { Button, Card, Checkbox, Chip, Field, Input, Select, Skeleton, cx } from "../../ui";
import { Note } from "../../ui/icons";
import { LISTINGS } from "../params";

/** One field, drawn from its kind. Every control carries the same `data-action`
 *  per kind rather than one per setting: it is one control the user meets
 *  several times, which is how the inventory counts a control (see
 *  `e2e/actions.ts`). What tells them apart on screen — and in a test — is the
 *  label, which `Field` wires to the control's id. */
function SetupInput({ field, settings, value, onChange }: {
  field: SetupField;
  settings: Settings;
  value: string | boolean;
  onChange: (next: string | boolean) => void;
}) {
  const t = useT();
  const label = t(fieldLabelKey(field.key));
  const hint = t(fieldHintKey(field.key));

  if (field.kind === "toggle") {
    return (
      <div className="space-y-1">
        <Checkbox data-action="setup.toggle" label={label} checked={value === true}
          onCheckedChange={(checked) => onChange(checked === true)} />
        <p className="text-2xs t-muted">{hint}</p>
      </div>
    );
  }

  if (field.kind === "select") {
    return (
      <Field label={label} hint={hint}>
        <Select data-action="setup.select" value={String(value)}
          onValueChange={onChange}
          options={optionsFor(field, settings).map((option) => ({
            value: option, label: t(optionLabelKey(option)),
          }))} />
      </Field>
    );
  }

  return (
    <Field label={label} hint={hint}>
      <Input data-action="setup.field"
        type={field.kind === "secret" ? "password" : field.kind === "number" ? "number" : "text"}
        step={field.kind === "number" ? (field.fractional ? "0.5" : "1") : undefined}
        min={field.kind === "number" ? 0 : undefined}
        autoComplete={field.kind === "secret" ? "off" : undefined}
        value={String(value)}
        onChange={(e) => onChange(e.target.value)} />
      {field.stored && (
        <div className="pt-0.5">
          <SecretStatus set={field.stored(settings)} dirty={String(value).trim() !== ""} />
        </div>
      )}
    </Field>
  );
}

/** What the backend already knows about this machine, said out loud on the step
 *  that would otherwise be tempted to ask. */
function Detected({ settings, t }: { settings: Settings; t: TFunction }) {
  const lines = [
    settings.datadome_harvester_available
      ? t("setup.detected.harvester") : t("setup.detected.noHarvester"),
    settings.camoufox_available ? t("setup.detected.camoufox") : null,
    settings.datadome_cookie_set
      ? t("setup.detected.cookie", { minutes: settings.datadome_cookie_ttl_minutes })
      : t("setup.detected.noCookie"),
  ].filter((line): line is string => line !== null);

  return (
    <div className="flex flex-wrap gap-1.5">
      {lines.map((line) => <Chip key={line} tone="neutral">{line}</Chip>)}
    </div>
  );
}

/** One step's form. Keyed by the group above, so moving on builds a new one and
 *  the seeding is the initial state rather than an effect that has to notice the
 *  step changed — and a secret typed on step one cannot leak into step two. */
function GroupForm({ group, settings, busy, canGoBack, onBack, onSkip, onSave, saveLabel }: {
  group: SetupGroup;
  settings: Settings;
  busy: boolean;
  canGoBack: boolean;
  onBack: () => void;
  onSkip: () => void;
  onSave: (payload: Partial<Settings>) => void;
  saveLabel: string;
}) {
  const t = useT();
  const [values, setValues] = useState<SetupValues>(() => seed(group, settings));

  function set(key: string, next: string | boolean) {
    setValues((current) => ({ ...current, [key]: next }));
  }

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <h3 className="font-medium">{t(groupTitleKey(group.id))}</h3>
        <p className="text-sm leading-relaxed t-muted">{t(groupBodyKey(group.id))}</p>
        {group.id === "unblocked" && <Detected settings={settings} t={t} />}
      </div>

      <div className="space-y-4">
        {fieldsFor(group, settings).map((field) => (
          <SetupInput key={field.key} field={field} settings={settings}
            value={values[field.key] ?? ""}
            onChange={(next) => set(field.key, next)} />
        ))}
      </div>

      <p className="flex items-start gap-2 text-xs leading-relaxed t-muted">
        <Note className="mt-0.5 shrink-0" />
        {t("setup.optional")}
      </p>

      <div className="flex flex-wrap items-center gap-2 pt-1">
        {canGoBack && (
          <Button data-action="setup.back" onClick={onBack} disabled={busy}>
            {t("setup.back")}
          </Button>
        )}
        <div className="flex-1" />
        {/* Skipping is the equal of saving here, so it is the same size and the
            same shape and sits beside it. A wizard whose only real control is
            the one that keeps going is a wizard that requires everything. */}
        <Button data-action="setup.skip" onClick={onSkip} disabled={busy}>
          {t("setup.skip")}
        </Button>
        {/* Solid accent on every step, with only the wording changing at the end.
            The button that swaps its own variant keeps its DOM node and starts a
            colour transition on the swap, which is a real failure this suite has
            already produced — see `e2e/harness/invariants.ts`. */}
        <Button data-action="setup.save" variant="solid" tone="accent" disabled={busy}
          onClick={() => onSave(payloadFor(group, values, settings))}>
          {busy ? t("common.saving") : saveLabel}
        </Button>
      </div>
    </div>
  );
}

export default function SetupRoute() {
  const t = useT();
  const toasts = useToasts();
  const navigate = useNavigate();
  // The same re-read the dialog does, and for the same reason: a wizard seeded
  // from a cached copy would be writing a snapshot back.
  const loaded = useSettingsForm();
  const save = useSaveSettings();
  const [index, setIndex] = useState(0);
  const [busy, setBusy] = useState(false);

  const settings = loaded.data ?? null;
  const group = groupAt(index);
  const atEnd = index === GROUPS.length - 1;

  /** Finishing, however it is reached. The flag is a setting rather than
   *  something in this browser: it is a fact about the install, so a second
   *  machine — and this one after an upgrade — is not asked all over again. */
  async function finish(payload: Partial<Settings>) {
    setBusy(true);
    try {
      await save.mutateAsync({ ...payload, setup_completed: true });
      void navigate(LISTINGS);
    } catch (e) {
      toasts.fail(e, { doing: t("toast.settingsSaveFailed") });
    } finally {
      setBusy(false);
    }
  }

  async function commit(payload: Partial<Settings>) {
    if (atEnd) return finish(payload);
    setBusy(true);
    try {
      // Nothing typed on this step is still a step: it moves on without a
      // request rather than posting an empty object at the backend.
      if (Object.keys(payload).length > 0) await save.mutateAsync(payload);
      setIndex(index + 1);
    } catch (e) {
      toasts.fail(e, { doing: t("toast.settingsSaveFailed") });
    } finally {
      setBusy(false);
    }
  }

  function skip() {
    if (atEnd) void finish({});
    else setIndex(index + 1);
  }

  return (
    <Card asChild padding="lg">
      <section className="max-w-3xl mx-auto space-y-5">
        <div className="space-y-1">
          <h2 className="font-semibold text-lg">{t("setup.title")}</h2>
          <p className="text-sm t-muted">{t("setup.intro")}</p>
        </div>

        <ol className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {GROUPS.map((each, position) => (
            <li key={each.id} aria-current={each.id === group.id ? "step" : undefined}
              className={cx("flex items-center gap-1.5",
                each.id === group.id ? "t-strong font-medium" : "t-muted")}>
              <span aria-hidden="true"
                className={cx(
                  "h-5 w-5 shrink-0 rounded-pill grid place-items-center font-bold",
                  each.id === group.id ? "bg-accent-surface text-accent-ink" : "border border-line",
                )}>
                {position + 1}
              </span>
              {t(groupTitleKey(each.id))}
            </li>
          ))}
        </ol>

        {settings ? (
          <GroupForm key={group.id} group={group} settings={settings} busy={busy}
            canGoBack={index > 0} onBack={() => setIndex(index - 1)}
            onSkip={skip} onSave={(payload) => void commit(payload)}
            saveLabel={atEnd ? t("setup.finish") : t("setup.saveNext")} />
        ) : (
          // The shape of the form that is coming, so the step does not read as
          // a wizard page whose question failed to arrive.
          <div>
            <Skeleton className="h-4 w-1/3" label={t("common.loading")} />
            <Skeleton className="mt-4 h-9 w-full" />
            <Skeleton className="mt-3 h-9 w-full" />
            <Skeleton className="mt-4 h-9 w-32" />
          </div>
        )}
      </section>
    </Card>
  );
}
