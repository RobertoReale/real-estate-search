import type { GroupedSearchProfile, SearchProfile } from "../types";

/**
 * Normalizes a profile name to its canonical base name across portals,
 * e.g. "Bicocca / Niguarda - Monolocale (immobiliare)" -> "Bicocca / Niguarda - Monolocale"
 */
export function getBaseName(name: string): string {
  if (!name) return "Untitled search";
  let cleaned = name;
  let prev = "";
  while (cleaned !== prev) {
    prev = cleaned;
    cleaned = cleaned
      .replace(/\s*[\(\[-]\s*(immobiliare|idealista)\s*[\)\]-]?\s*$/i, "")
      .replace(/\s+-\s+(immobiliare|idealista)\s*$/i, "")
      .trim();
  }
  return cleaned || name.trim() || "Untitled search";
}

/**
 * Groups raw SearchProfiles into unified GroupedSearchProfiles (`GroupedSearchProfile[]`),
 * consolidating multiple portal entries for the same logical search into a single card/box.
 */
export function groupSearchProfiles(profiles: SearchProfile[]): GroupedSearchProfile[] {
  const map = new Map<string, SearchProfile[]>();
  for (const p of profiles) {
    const base = getBaseName(p.name).toLowerCase();
    const existing = map.get(base) || [];
    existing.push(p);
    map.set(base, existing);
  }

  const result: GroupedSearchProfile[] = [];
  for (const [, group] of map.entries()) {
    // Sort profiles: immobiliare first, then idealista, then others by ID
    group.sort((a, b) => {
      const order: Record<string, number> = { immobiliare: 1, idealista: 2 };
      const oa = order[a.portal] || 99;
      const ob = order[b.portal] || 99;
      if (oa !== ob) return oa - ob;
      return a.id - b.id;
    });

    const baseName = getBaseName(group[0].name);
    const ids = group.map((g) => g.id);
    const portals = Array.from(new Set(group.map((g) => g.portal)));
    const is_active = group.every((g) => g.is_active);
    const notify_channels = group[0].notify_channels || "";
    const consecutive_failures = Math.max(...group.map((g) => g.consecutive_failures || 0));

    // Status priority: error > blocked > ok
    let last_run_status = "ok";
    if (group.some((g) => g.last_run_status === "error")) {
      last_run_status = "error";
    } else if (group.some((g) => g.last_run_status === "blocked")) {
      last_run_status = "blocked";
    } else if (group.some((g) => g.last_run_status === "ok")) {
      last_run_status = "ok";
    } else {
      last_run_status = group[0].last_run_status || "";
    }

    const details = group
      .map((g) => g.last_run_detail)
      .filter(Boolean)
      .join(" · ");

    result.push({
      baseName,
      profiles: group,
      ids,
      portals,
      is_active,
      notify_channels,
      consecutive_failures,
      last_run_status,
      last_run_detail: details,
      excluded_keywords: group[0].excluded_keywords || "",
    });
  }
  return result;
}
