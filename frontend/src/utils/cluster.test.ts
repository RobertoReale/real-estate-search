/** The map's pin grouping, exercised without a map: `clusterByGrid` takes the
 *  projection as an argument precisely so these can use a straight one. */
import { describe, expect, it } from "vitest";
import { clusterByGrid, type Placed } from "./cluster";

/** One degree is one pixel, so a cell of 10 is a 10°×10° square and the
 *  expected grouping can be read straight off the coordinates. */
const flat = (lat: number, lng: number) => ({ x: lng, y: lat });

const at = (lat: number, lng: number, id = 0): Placed & { id: number } => ({ lat, lng, id });

describe("clusterByGrid", () => {
  it("leaves points in separate cells alone, each on its own coordinate", () => {
    const groups = clusterByGrid([at(1, 1, 1), at(1, 25, 2), at(45, 1, 3)], flat, 10);
    expect(groups).toHaveLength(3);
    expect(groups.map((g) => g.items.length)).toEqual([1, 1, 1]);
    // a lone point is drawn exactly where it is, not at the centre of its cell
    expect(groups[0]).toMatchObject({ lat: 1, lng: 1 });
  });

  it("groups points that share a cell and draws them at their mean", () => {
    const groups = clusterByGrid([at(1, 1, 1), at(3, 3, 2), at(5, 5, 3)], flat, 10);
    expect(groups).toHaveLength(1);
    expect(groups[0].items.map((p) => p.id)).toEqual([1, 2, 3]);
    expect(groups[0].lat).toBeCloseTo(3);
    expect(groups[0].lng).toBeCloseTo(3);
  });

  it("splits a group as the cell shrinks, which is what zooming in does", () => {
    const points = [at(1, 1, 1), at(1, 9, 2)];
    expect(clusterByGrid(points, flat, 10)).toHaveLength(1);
    expect(clusterByGrid(points, flat, 4)).toHaveLength(2);
  });

  it("groups by projected pixels, not by degrees", () => {
    // the same two points, at a projection twice as fine: 8° apart becomes 16px
    const points = [at(1, 1, 1), at(1, 9, 2)];
    const zoomed = (lat: number, lng: number) => ({ x: lng * 2, y: lat * 2 });
    expect(clusterByGrid(points, flat, 10)).toHaveLength(1);
    expect(clusterByGrid(points, zoomed, 10)).toHaveLength(2);
  });

  it("keeps the input order, both of the groups and inside them", () => {
    const groups = clusterByGrid(
      [at(1, 1, 1), at(1, 25, 2), at(2, 2, 3), at(2, 26, 4)],
      flat,
      10,
    );
    expect(groups.map((g) => g.items.map((p) => p.id))).toEqual([
      [1, 3],
      [2, 4],
    ]);
  });

  it("drops a point that will not project, instead of pooling every one of them", () => {
    const groups = clusterByGrid([at(1, 1, 1), at(NaN, NaN, 2), at(50, 50, 3)], flat, 10);
    expect(groups.flatMap((g) => g.items.map((p) => p.id))).toEqual([1, 3]);
  });

  it("refuses a cell that cannot be a square of pixels", () => {
    expect(() => clusterByGrid([at(1, 1)], flat, 0)).toThrow(RangeError);
    expect(() => clusterByGrid([at(1, 1)], flat, -5)).toThrow(RangeError);
  });

  it("handles an empty set without inventing a group", () => {
    expect(clusterByGrid([], flat, 10)).toEqual([]);
  });
});
