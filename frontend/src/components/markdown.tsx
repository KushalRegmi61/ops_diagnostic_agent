"use client";

/**
 * Tiny dependency-free Markdown renderer for the model's blueprint claims.
 *
 * Supports the subset the lead-agent prompts actually produce: bold, italic,
 * inline code, links, headings, ordered & unordered lists, blockquotes, fenced
 * code blocks, horizontal rules, and paragraphs. Anything we don't recognize
 * falls through as plain text — safe by default since we never inject raw HTML.
 */

import { Fragment, ReactNode } from "react";

type Block =
  | { kind: "heading"; level: 1 | 2 | 3 | 4; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "quote"; lines: string[] }
  | { kind: "code"; lang: string; body: string }
  | { kind: "hr" }
  | { kind: "p"; text: string };

/** Escape any HTML so model output can't inject markup; we only render text + our tags. */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** Apply inline transforms (bold, italic, code, links) to an escaped string. */
function renderInline(escaped: string): string {
  let out = escaped;
  // inline code first so its contents are protected from other transforms
  out = out.replace(/`([^`]+)`/g, (_m, code) => `<code>${code}</code>`);
  // links [label](url)
  out = out.replace(
    /\[([^\]]+)\]\(([^)\s]+)\)/g,
    (_m, label, url) =>
      `<a href="${url}" target="_blank" rel="noreferrer noopener">${label}</a>`,
  );
  // bold **text** or __text__
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  // italic *text* or _text_
  out = out.replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<em>$2</em>");
  out = out.replace(/(^|[\s(])_([^_\n]+)_/g, "$1<em>$2</em>");
  return out;
}

/** Parse a markdown string into ordered structural blocks. */
function parseBlocks(src: string): Block[] {
  const lines = src.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const raw = lines[i];
    const line = raw.trimEnd();

    if (line.trim() === "") {
      i++;
      continue;
    }

    // fenced code
    if (/^```/.test(line)) {
      const lang = line.replace(/^```/, "").trim();
      const buf: string[] = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) {
        buf.push(lines[i]);
        i++;
      }
      i++; // closing fence
      blocks.push({ kind: "code", lang, body: buf.join("\n") });
      continue;
    }

    // hr
    if (/^\s*(\*\s*\*\s*\*|-{3,}|_{3,})\s*$/.test(line)) {
      blocks.push({ kind: "hr" });
      i++;
      continue;
    }

    // headings
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      blocks.push({
        kind: "heading",
        level: heading[1].length as 1 | 2 | 3 | 4,
        text: heading[2].trim(),
      });
      i++;
      continue;
    }

    // blockquote
    if (/^>\s?/.test(line)) {
      const buf: string[] = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        buf.push(lines[i].replace(/^>\s?/, ""));
        i++;
      }
      blocks.push({ kind: "quote", lines: buf });
      continue;
    }

    // unordered list
    if (/^\s*[-*+]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*+]\s+/, ""));
        i++;
      }
      blocks.push({ kind: "ul", items });
      continue;
    }

    // ordered list
    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i++;
      }
      blocks.push({ kind: "ol", items });
      continue;
    }

    // paragraph — accumulate until blank line / new block trigger
    const buf: string[] = [line];
    i++;
    while (i < lines.length) {
      const next = lines[i];
      if (
        next.trim() === "" ||
        /^#{1,4}\s+/.test(next) ||
        /^```/.test(next) ||
        /^>\s?/.test(next) ||
        /^\s*[-*+]\s+/.test(next) ||
        /^\s*\d+\.\s+/.test(next) ||
        /^\s*(\*\s*\*\s*\*|-{3,}|_{3,})\s*$/.test(next)
      ) {
        break;
      }
      buf.push(next.trimEnd());
      i++;
    }
    blocks.push({ kind: "p", text: buf.join(" ") });
  }

  return blocks;
}

/** Render one inline string as React via dangerouslySetInnerHTML on an escaped+transformed payload. */
function Inline({ text }: { text: string }) {
  return (
    <span
      dangerouslySetInnerHTML={{ __html: renderInline(escapeHtml(text)) }}
    />
  );
}

/** Render a parsed list of blocks. */
function renderBlocks(blocks: Block[]): ReactNode {
  return blocks.map((b, idx) => {
    const key = `b-${idx}`;
    switch (b.kind) {
      case "heading": {
        const Tag = (`h${b.level}` as unknown) as keyof React.JSX.IntrinsicElements;
        return (
          <Tag key={key}>
            <Inline text={b.text} />
          </Tag>
        );
      }
      case "ul":
        return (
          <ul key={key}>
            {b.items.map((it, i) => (
              <li key={`${key}-i-${i}`}>
                <Inline text={it} />
              </li>
            ))}
          </ul>
        );
      case "ol":
        return (
          <ol key={key}>
            {b.items.map((it, i) => (
              <li key={`${key}-i-${i}`}>
                <Inline text={it} />
              </li>
            ))}
          </ol>
        );
      case "quote":
        return (
          <blockquote key={key}>
            {b.lines.map((l, i) => (
              <Fragment key={`${key}-q-${i}`}>
                <Inline text={l} />
                {i < b.lines.length - 1 ? <br /> : null}
              </Fragment>
            ))}
          </blockquote>
        );
      case "code":
        return (
          <pre key={key}>
            <code>{b.body}</code>
          </pre>
        );
      case "hr":
        return <hr key={key} />;
      case "p":
        return (
          <p key={key}>
            <Inline text={b.text} />
          </p>
        );
    }
  });
}

/** Public Markdown renderer — set `compact` for tighter spacing inside cards. */
export function Markdown({
  source,
  compact = false,
  className = "",
}: {
  source: string;
  compact?: boolean;
  className?: string;
}) {
  if (!source) return null;
  const blocks = parseBlocks(source.trim());
  return (
    <div className={`md ${compact ? "md-compact" : ""} ${className}`.trim()}>
      {renderBlocks(blocks)}
    </div>
  );
}
