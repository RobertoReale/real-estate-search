/** Finds every interactive element in the source, so the inventory cannot lie.
 *
 *  The runtime half of A.5 can only see controls a test managed to reach. This
 *  is the half that sees the ones it did not: a pass over `src/` that collects
 *  every JSX element carrying a `React` handler and reports whether it declares
 *  a `data-action`. A button added tomorrow with no entry turns the build red
 *  the same day, rather than shipping untried because nobody thought to test it.
 *
 *  Why a hand-written scanner rather than a parser: TypeScript 7's compiler is
 *  the native binary, its JavaScript API surface is not something to build a
 *  gate on, and nothing else in this project's dependency list parses TSX. What
 *  the gate actually needs is small — the name of each opening tag and the text
 *  of its attributes — and that is a lexer, not a parser. It tracks strings,
 *  both comment styles, and JSX expression containers (so a handler written
 *  inside `onClick={() => ...}` cannot be mistaken for the end of the tag), and
 *  it keeps a stack so an element nested inside an attribute expression is
 *  attributed to itself rather than to the tag around it.
 */
import fs from "node:fs";
import path from "node:path";

/** The props that make an element something a user can operate. `<form>` is in
 *  the list as a tag rather than a prop: its submit can be raised by pressing
 *  Enter in any field it contains, so it is a control even when the handler
 *  sits somewhere else. */
const HANDLER = /\bon(Click|Change|Submit|KeyDown)\s*=/;

export interface Element {
  /** Repo-relative path, forward slashes, for a message someone can act on. */
  readonly file: string;
  readonly line: number;
  readonly tag: string;
  /** The declared id, or null for a handler-bearing element without one. */
  readonly action: string | null;
  /** True when `data-action={...}` is an expression rather than a literal —
   *  a component that names its own instances (Calculators' `Field`, the
   *  export and view switches). The value is checked at runtime instead: the
   *  recorder refuses an id the inventory does not carry. */
  readonly dynamic: boolean;
}

interface Open {
  name: string;
  start: number;
  depth: number;
  attrs: string;
}

/** Every opening tag in one file, with its depth-0 attribute text. */
function tags(src: string): Open[] {
  const done: Open[] = [];
  const stack: Open[] = [];
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    const top = stack[stack.length - 1];

    if (c === "/" && src[i + 1] === "/") {
      const end = src.indexOf("\n", i);
      i = end === -1 ? src.length : end;
      continue;
    }
    if (c === "/" && src[i + 1] === "*") {
      const end = src.indexOf("*/", i + 2);
      i = end === -1 ? src.length : end + 2;
      continue;
    }
    // {/* ... */} — a JSX comment, which is a brace the depth counter must not
    // see, or every tag after one in the same element runs to the file's end.
    if (c === "{" && top && src[i + 1] === "/" && src[i + 2] === "*") {
      const end = src.indexOf("*/}", i);
      i = end === -1 ? src.length : end + 3;
      continue;
    }
    if (c === '"' || c === "'" || c === "`") {
      let j = i + 1;
      while (j < src.length) {
        if (src[j] === "\\") { j += 2; continue; }
        if (src[j] === c) break;
        j++;
      }
      if (top && top.depth === 0) top.attrs += src.slice(i, j + 1);
      i = j + 1;
      continue;
    }
    if (c === "<" && /[A-Za-z]/.test(src[i + 1] ?? "")) {
      const m = /^<([A-Za-z][\w.]*)/.exec(src.slice(i));
      if (m) {
        stack.push({ name: m[1], start: i, depth: 0, attrs: "" });
        i += m[0].length;
        continue;
      }
    }
    if (top) {
      if (c === "{") { top.depth++; i++; continue; }
      if (c === "}") { top.depth = Math.max(0, top.depth - 1); i++; continue; }
      if (c === ">" && top.depth === 0) {
        done.push(stack.pop()!);
        i++;
        continue;
      }
      if (top.depth === 0) top.attrs += c;
    }
    i++;
  }
  return done;
}

function sources(dir: string, found: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) sources(full, found);
    // Tests render components; they do not ship them, and a handler written in
    // one is not a control a user can reach.
    else if (/\.tsx?$/.test(entry.name) && !/\.test\./.test(entry.name)) found.push(full);
  }
  return found;
}

/**
 * Every interactive element under `root`, in file order.
 *
 * Only intrinsic elements — a lowercase tag is a DOM node that will carry the
 * attribute, while `<PropertyCard onClick={...}>` is a prop being passed to a
 * component that decides for itself what to do with it. Requiring an id there
 * would mean requiring one on something that never reaches the page.
 */
export function interactiveElements(root: string): Element[] {
  const out: Element[] = [];
  for (const file of sources(root)) {
    const src = fs.readFileSync(file, "utf8");
    for (const tag of tags(src)) {
      if (!/^[a-z]/.test(tag.name)) continue;
      if (!HANDLER.test(tag.attrs) && tag.name !== "form") continue;
      const literal = /data-action\s*=\s*"([^"]*)"/.exec(tag.attrs);
      const any = /data-action\s*=/.test(tag.attrs);
      out.push({
        file: path.relative(root, file).replace(/\\/g, "/"),
        line: src.slice(0, tag.start).split("\n").length,
        tag: tag.name,
        action: literal ? literal[1] : null,
        dynamic: any && !literal,
      });
    }
  }
  return out;
}

/** Whether an id appears anywhere in the source as a literal string. The other
 *  direction of the same gate: an inventory that outlives the control it
 *  describes is a list nobody trusts, and a dynamic `data-action` is only
 *  honest if the value it can take is written down somewhere. */
export function literalsInSource(root: string): Set<string> {
  const found = new Set<string>();
  for (const file of sources(root)) {
    for (const m of fs.readFileSync(file, "utf8").matchAll(/"([a-z][\w.]*\.[\w.]+)"/g)) {
      found.add(m[1]);
    }
  }
  return found;
}
