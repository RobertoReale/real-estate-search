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
