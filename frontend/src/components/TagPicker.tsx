import { useRef, useState } from "react";
import type { Tag } from "../types";

interface Props {
  tags: Tag[];       // this property's current tags
  allTags: Tag[];     // global tag list, for the autocomplete suggestions
  onAdd: (name: string) => void;
  onRemove: (tagId: number) => void;
  /** Compact mode (card): smaller chips, "+" opens a narrower popover. */
  compact?: boolean;
}

/** Freeform chip editor for a property's tags: existing tags render as
 *  removable chips, a trailing "+" opens a small text input that suggests
 *  matching existing tags (click to add) or, with no exact match, offers to
 *  create a new one on Enter. Used identically from PropertyCard (while
 *  browsing the grid) and PropertyModal, so classifying a listing never
 *  requires opening the modal first. */
export default function TagPicker({ tags, allTags, onAdd, onRemove, compact }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const currentIds = new Set(tags.map((t) => t.id));
  const trimmed = query.trim();
  const suggestions = trimmed
    ? allTags.filter(
        (t) => !currentIds.has(t.id) && t.name.toLowerCase().includes(trimmed.toLowerCase())
      )
    : allTags.filter((t) => !currentIds.has(t.id));
  const exactMatch = allTags.some((t) => t.name.toLowerCase() === trimmed.toLowerCase());

  function commit(name: string) {
    const clean = name.trim();
    if (!clean) return;
    onAdd(clean);
    setQuery("");
    setOpen(false);
  }

  function closeOnBlur(e: React.FocusEvent<HTMLDivElement>) {
    if (!containerRef.current?.contains(e.relatedTarget as Node)) {
      setOpen(false);
      setQuery("");
    }
  }

  return (
    <div
      ref={containerRef}
      className="flex flex-wrap items-center gap-1"
      onClick={(e) => e.stopPropagation()}
      onBlur={closeOnBlur}>
      {tags.map((t) => (
        <span key={t.id}
          className={`inline-flex items-center gap-1 rounded-full bg-slate-200 text-slate-700
            dark:bg-slate-700 dark:text-slate-200 ${compact ? "text-[10px] px-2 py-0.5" : "text-xs px-2.5 py-1"}`}>
          {t.name}
          <button type="button" className="opacity-60 hover:opacity-100"
            title={`Remove tag "${t.name}"`} aria-label={`Remove tag "${t.name}"`}
            onClick={() => onRemove(t.id)}>
            ×
          </button>
        </span>
      ))}
      {!open && (
        <button type="button"
          className={`rounded-full border border-dashed border-slate-400 text-slate-500
            dark:border-slate-500 dark:text-slate-400 hover:border-blue-500 hover:text-blue-500
            ${compact ? "text-[10px] px-2 py-0.5" : "text-xs px-2.5 py-1"}`}
          title="Add tag" aria-label="Add tag"
          onClick={() => setOpen(true)}>
          + tag
        </button>
      )}
      {open && (
        <div className="relative">
          <input
            autoFocus
            className="input text-xs w-32 py-1"
            placeholder="Tag name…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commit(query);
              if (e.key === "Escape") { setOpen(false); setQuery(""); }
            }}
          />
          {(suggestions.length > 0 || (trimmed && !exactMatch)) && (
            <div className="absolute z-10 mt-1 w-40 max-h-48 overflow-auto rounded-lg
              glass shadow-lg p-1">
              {suggestions.map((t) => (
                <button key={t.id} type="button"
                  className="block w-full text-left text-xs px-2 py-1 rounded hover:bg-blue-500/20"
                  onClick={() => commit(t.name)}>
                  {t.name}
                </button>
              ))}
              {trimmed && !exactMatch && (
                <button type="button"
                  className="block w-full text-left text-xs px-2 py-1 rounded hover:bg-blue-500/20 font-medium"
                  onClick={() => commit(trimmed)}>
                  + create "{trimmed}"
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
