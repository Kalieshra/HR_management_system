#!/usr/bin/env node
/**
 * Fails when a component uses a *physical* Tailwind utility.
 *
 * The whole product is bidirectional (Arabic RTL by default, English LTR), so
 * spacing and alignment must be expressed with logical utilities:
 *
 *   ml-*  -> ms-*      pl-*        -> ps-*        left-*       -> start-*
 *   mr-*  -> me-*      pr-*        -> pe-*        right-*      -> end-*
 *   text-left -> text-start        border-l-*    -> border-s-*
 *   text-right -> text-end         rounded-l-*   -> rounded-s-*
 *
 * Directional icons flip with `rtl:rotate-180` instead.
 *
 * Only string literals are scanned (comments and identifiers are stripped
 * first), so prose like "the right base URL" is not a violation. Add
 * `check-rtl-ignore` to a line to skip it.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname;
const SRC = join(ROOT, 'src');
const CODE_EXTENSIONS = ['.ts', '.tsx'];
const STYLE_EXTENSIONS = ['.css'];

const VARIANTS = '(?:[a-z0-9-]+:)*';
// Utilities that always carry a value: `ml-4`, `left-0`, `pe-[2px]`.
const VALUED = '(?:ml|mr|pl|pr|left|right)-[a-z0-9./%[\\]-]+';
// Utilities valid on their own, with an optional value: `border-l`, `text-left`.
const BARE =
  '(?:border-l|border-r|rounded-l|rounded-r|text-left|text-right|float-left|float-right)(?:-[a-z0-9./%[\\]-]+)?';

const CLASS_TOKEN = new RegExp(`(?:^|\\s)(-?${VARIANTS}(?:${VALUED}|${BARE}))(?=\\s|$)`, 'g');
const STRING_LITERAL = /"([^"\n]*)"|'([^'\n]*)'|`([^`\n]*)`/g;

/** Remove `//` line comments (not `https://`) and `/* *\/` block comments. */
function stripComments(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/(^|[^:])\/\/.*$/gm, '$1');
}

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) yield* walk(full);
    else yield full;
  }
}

const violations = [];

for (const file of walk(SRC)) {
  const isCode = CODE_EXTENSIONS.some((ext) => file.endsWith(ext));
  const isStyle = STYLE_EXTENSIONS.some((ext) => file.endsWith(ext));
  if (!isCode && !isStyle) continue;

  const lines = stripComments(readFileSync(file, 'utf8')).split('\n');

  lines.forEach((line, index) => {
    if (line.includes('check-rtl-ignore')) return;

    // In code, only class strings can hold utilities; in CSS, scan the line.
    const haystacks = isCode
      ? [...line.matchAll(STRING_LITERAL)].map((m) => m[1] ?? m[2] ?? m[3] ?? '')
      : [line];

    for (const haystack of haystacks) {
      for (const match of haystack.matchAll(CLASS_TOKEN)) {
        violations.push({ file: relative(ROOT, file), line: index + 1, utility: match[1] });
      }
    }
  });
}

if (violations.length > 0) {
  console.error('\nPhysical Tailwind utilities found — use logical ones instead:\n');
  for (const v of violations) {
    console.error(`  ${v.file}:${v.line}  ${v.utility}`);
  }
  console.error(`\n${violations.length} violation(s).\n`);
  process.exit(1);
}

console.log('rtl-check: no physical Tailwind utilities found.');
