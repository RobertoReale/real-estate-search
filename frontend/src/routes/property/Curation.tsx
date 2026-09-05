/** The two things on this page that are the user's own: the tags they file a
 *  property under and the note they keep about it.
 *
 *  Nothing a scan does ever touches either (invariant 8), which is why they sit
 *  together and away from everything the backend computes.
 */
import { useState } from "react";
import { useT } from "../../i18n";
import { useSaveNotes } from "../../queries/properties";
import type { Property, Tag } from "../../types";
import { Button, Textarea } from "../../ui";
import { Notes, Tags } from "../../ui/icons";
import TagPicker from "../../components/TagPicker";
import { useToasts } from "../../components/Toast";

const HEADING = "flex items-center gap-1.5 font-semibold mb-2 text-sm uppercase t-muted";

interface Props {
  property: Property;
  allTags: Tag[];
  onAddTag: (name: string) => void;
  onRemoveTag: (tagId: number) => void;
}

export function Curation({ property: p, allTags, onAddTag, onRemoveTag }: Props) {
  const t = useT();
  const toasts = useToasts();
  const [notes, setNotes] = useState(p.notes);
  const saveNotesTo = useSaveNotes();
  const dirty = notes !== p.notes;

  async function save() {
    try {
      await saveNotesTo.mutateAsync({ id: p.id, notes });
    } catch (e) {
      // the unsaved text stays in the textarea, so a retry costs one click
      toasts.fail(e, { doing: t("detail.notesError"), retry: () => save() });
    }
  }

  return (
    <div className="space-y-6">
      <section>
        <h3 className={HEADING}><Tags /> {t("detail.tags")}</h3>
        <TagPicker tags={p.tags} allTags={allTags} onAdd={onAddTag} onRemove={onRemoveTag} />
      </section>

      <section>
        <h3 className={HEADING}><Notes /> {t("detail.notes")}</h3>
        <Textarea data-action="detail.notes"
          className="h-24 !resize-none"
          placeholder={t("detail.notesPlaceholder")}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
        {dirty && (
          <div className="flex justify-end mt-2">
            <Button data-action="detail.notes.save" variant="solid" tone="accent"
              onClick={save} disabled={saveNotesTo.isPending}>
              {saveNotesTo.isPending ? t("common.saving") : t("detail.saveNotes")}
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}
