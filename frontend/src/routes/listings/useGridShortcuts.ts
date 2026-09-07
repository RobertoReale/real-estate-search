/** Reading the results without the mouse.
 *
 *  Two things a reader does with a list: move through it, and mark something in
 *  it. `j`/`k` step the focus from card to card and `f` favourites the card the
 *  focus is on — the same three keys a mail client has, for the same reason.
 *
 *  Driven through the DOM rather than through React state, and deliberately.
 *  The focus is the browser's: whatever the user reached with Tab or clicked on
 *  is where `j` continues from, and *moving the focus* is what a screen reader
 *  announces and what the card's own `onFocus` uses to light the pin beside it.
 *  A parallel "current index" in state would have to be kept in step with the
 *  real focus, and the two would disagree the first time a card was clicked.
 *
 *  `f` clicks the star rather than calling the mutation, so the key and the
 *  pointer go through one code path and the confirmation, the undo and the
 *  failure message are the ones already written for the button.
 */
import { useShortcuts } from "../../hooks/useShortcuts";

/** A card. `data-property-id` is on the card and on nothing else. */
const CARD = "[data-property-id]";
/** Where the focus lands on a card: the title, which is its keyboard route in. */
const ENTRY = "[data-action='property.open']";
const FAVORITE = "[data-action='property.favorite']";

function cards(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>(CARD));
}

/** The card the focus is inside, if it is inside one. */
function focused(): HTMLElement | null {
  const active = document.activeElement;
  return active instanceof Element ? active.closest<HTMLElement>(CARD) : null;
}

export function useGridShortcuts(enabled: boolean): void {
  /** Move the focus one card along, or decline the key. */
  function move(by: 1 | -1): boolean | void {
    const all = cards();
    const from = focused();
    // Nothing focused yet: `j` starts at the top of the results, `k` has
    // nowhere to come back from.
    const index = from === null ? (by === 1 ? 0 : -1) : all.indexOf(from) + by;
    const next = all[index];
    // Off either end, or no results at all. Leave the key to the browser rather
    // than swallow the page's own scrolling to say "no".
    if (next === undefined || index < 0) return false;
    (next.querySelector<HTMLElement>(ENTRY) ?? next).focus();
    // `nearest` and only nearest: a card already on screen must not move.
    next.scrollIntoView({ block: "nearest" });
  }

  useShortcuts([
    { keys: ["j"], run: () => move(1) },
    { keys: ["k"], run: () => move(-1) },
    {
      keys: ["f"],
      run: () => {
        const star = focused()?.querySelector<HTMLElement>(FAVORITE);
        // `f` with the focus somewhere else entirely is not a favourite that
        // failed, it is a letter meant for something else.
        if (!star) return false;
        star.click();
      },
    },
  ], enabled);
}
