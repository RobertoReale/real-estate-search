/** The frame parser, which is the half of the event stream nothing else can see.
 *
 *  Everything downstream of it is asserted in the browser suite, on the product:
 *  the grid re-reading itself, the timers staying silent, the reconnection. This
 *  is the part that cannot be — a chunk boundary falls wherever the network puts
 *  it, so "a frame arrived in two pieces" is a case that happens constantly in
 *  production and never once in a run somebody watches.
 */
import { describe, expect, it } from "vitest";
import { parseFrames } from "./events";

describe("parseFrames", () => {
  it("reads a complete frame", () => {
    const { events, rest } = parseFrames('event: status\ndata: {"running":true}\n\n');
    expect(events).toEqual([{ topic: "status", data: { running: true } }]);
    expect(rest).toBe("");
  });

  it("holds a half-arrived frame back until the rest of it lands", () => {
    const first = parseFrames('event: status\ndata: {"run');
    expect(first.events).toEqual([]);

    const second = parseFrames(first.rest + 'ning":true}\n\n');
    expect(second.events).toEqual([{ topic: "status", data: { running: true } }]);
  });

  it("reads several frames out of one chunk", () => {
    const { events } = parseFrames(
      'event: status\ndata: {"running":false}\n\nevent: health\ndata: {"version":"a"}\n\n',
    );
    expect(events.map((e) => e.topic)).toEqual(["status", "health"]);
  });

  it("ignores the heartbeat", () => {
    // It carries nothing; it exists so a socket that died quietly is noticed.
    const { events } = parseFrames(": ping\n\n");
    expect(events).toEqual([]);
  });

  it("skips a frame it cannot read rather than dropping the connection", () => {
    // The next frame on that topic is a whole snapshot too, so throwing away
    // the stream over one bad body would cost more than the body was worth.
    const { events } = parseFrames(
      "event: status\ndata: {not json\n\nevent: health\ndata: {\"version\":\"a\"}\n\n",
    );
    expect(events).toEqual([{ topic: "health", data: { version: "a" } }]);
  });
});
