// Extends Vitest's expect with jest-dom matchers (toBeInTheDocument, etc.) so
// future component tests can use them. Loaded via vite.config.ts setupFiles.
import "@testing-library/jest-dom/vitest";

// jsdom implements the DOM, not the browser: it has no layout and no pointer
// capture, so three APIs that every real engine provides are simply missing.
// Radix uses all three — pointer capture to tell a drag from a click on a
// listbox, scrollIntoView to keep the highlighted option visible, ResizeObserver
// to reposition a floating panel — and calls them unconditionally, because in a
// browser they are always there. Without these stubs the Select and Popover
// tests fail on "is not a function" before they ever reach an assertion.
//
// Stubs, deliberately: they do nothing and report nothing captured, which is the
// truthful answer in an environment with no pointer and no viewport. What the
// tests here assert is keyboard operation and the accessibility tree, neither of
// which depends on layout; anything that does needs the browser suite instead.
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// jsdom has no media queries either, and this one is not inert: `useMediaQuery`
// decides whether the filter rail renders inline or as a sheet, so a stub that
// always answered `false` would mean every component test drives a rail that is
// shut inside a sheet. jsdom does report a window width (1024), so answer from
// it rather than from a constant — a test that sets `window.innerWidth` gets
// the layout it asked for, and the default is the desktop one the specs expect.
if (!window.matchMedia) {
  window.matchMedia = (query: string): MediaQueryList => {
    const min = /\(min-width:\s*(\d+)px\)/.exec(query);
    const max = /\(max-width:\s*(\d+)px\)/.exec(query);
    const matches =
      (min === null || window.innerWidth >= Number(min[1])) &&
      (max === null || window.innerWidth <= Number(max[1]));
    return {
      matches, media: query, onchange: null,
      addEventListener: () => {}, removeEventListener: () => {},
      addListener: () => {}, removeListener: () => {},
      dispatchEvent: () => false,
    };
  };
}
