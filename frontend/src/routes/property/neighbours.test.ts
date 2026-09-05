/** Moving through the set: the arithmetic, away from the keyboard and the DOM.
 *
 *  The ends are the whole point. A traversal that wrapped round would hide from
 *  the user that they have seen everything, and one that ran off the end would
 *  navigate to `/listings/undefined`.
 */
import { describe, expect, it } from "vitest";
import type { Property } from "../../types";
import { neighbours } from "./neighbours";

const set = [11, 22, 33].map((id) => ({ id }) as Property);

describe("the neighbours of a property in the grid", () => {
  it("finds the one before and the one after", () => {
    expect(neighbours(set, 22)).toEqual({
      position: 2, total: 3, previous: 11, next: 33,
    });
  });

  it("stops at the first and at the last rather than wrapping", () => {
    expect(neighbours(set, 11).previous).toBeNull();
    expect(neighbours(set, 11).next).toBe(22);
    expect(neighbours(set, 33).next).toBeNull();
    expect(neighbours(set, 33).previous).toBe(22);
  });

  it("has nothing to offer for a property the set does not hold", () => {
    // A link whose filters exclude the property it points at: it still opens,
    // and there is simply no next one.
    expect(neighbours(set, 99)).toEqual({
      position: null, total: 3, previous: null, next: null,
    });
  });

  it("survives an empty set, which is what a cold deep link starts from", () => {
    expect(neighbours([], 11)).toEqual({
      position: null, total: 0, previous: null, next: null,
    });
  });
});
