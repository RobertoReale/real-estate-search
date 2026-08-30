/** Shared portal badge (Immobiliare.it / Idealista): the "chip" variant sits on
 *  panels/list rows, the "overlay" variant sits on top of a property photo. */
export function PortalBadge({
  portal, variant = "chip",
}: { portal: string; variant?: "chip" | "overlay" }) {
  const isImmobiliare = portal === "immobiliare";
  // The overlay sits on a property photo, so its fill is opaque and a shade
  // darker than the chip's: white on a translucent 600 lands at 3.1–4.1:1
  // depending on the picture underneath it, and the 700 weights clear 4.5:1
  // whatever is behind them.
  const cls =
    variant === "overlay"
      ? `${isImmobiliare ? "bg-blue-700" : "bg-lime-700"} text-white`
      : isImmobiliare ? "chip-blue" : "chip-lime";
  return (
    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-lg shrink-0 ${cls}`}>
      {portal}
    </span>
  );
}
