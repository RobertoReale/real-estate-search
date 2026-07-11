/** Shared portal badge (Immobiliare.it / Idealista): the "chip" variant sits on
 *  panels/list rows, the "overlay" variant sits on top of a property photo. */
export function PortalBadge({
  portal, variant = "chip",
}: { portal: string; variant?: "chip" | "overlay" }) {
  const isImmobiliare = portal === "immobiliare";
  const cls =
    variant === "overlay"
      ? `${isImmobiliare ? "bg-blue-600/80" : "bg-lime-600/80"} text-white backdrop-blur`
      : isImmobiliare ? "chip-blue" : "chip-lime";
  return (
    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-lg shrink-0 ${cls}`}>
      {portal}
    </span>
  );
}
