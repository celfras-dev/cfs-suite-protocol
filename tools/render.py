"""Markdown + generated tables -> one HTML page.

The same page is both the website body and the PDF source, so nothing is
written twice. Prose carries {{table:...}} placeholders; every table comes
from spec/_generated so the three language editions cannot drift apart.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import markdown
from jinja2 import Template

ASSETS = Path(__file__).resolve().parent.parent / "spec" / "assets"

LANG_FONTS = {
    "en": '"Segoe UI", Arial, Helvetica, sans-serif',
    "ko": '"Noto Sans KR", "Malgun Gothic", sans-serif',
    "zh": '"Microsoft YaHei", "Noto Sans SC", sans-serif',
}

LANG_TITLE = {
    "en": "Celfras Standard Protocol",
    "ko": "Celfras Standard Protocol",
    "zh": "Celfras Standard Protocol",
}

_PLACEHOLDER = re.compile(r"\{\{table:([a-z_]+)(?::([a-z_0-9]+))?\}\}")

# Loose, case-insensitive net for anything table-ish left over after
# _PLACEHOLDER has already consumed every well-formed placeholder. Wrong
# case (`{{table:opcodes:CORE}}`), wrong separator (`{{table:opcodes-core}}`),
# stray spaces (`{{ table:opcodes:core }}`) and an un-split kind:arg
# (`{{table:par16}}`) are all realistic authoring typos, and all of them
# still contain "table" between a `{{` and a `}}`. We deliberately do NOT
# flag every stray `{{...}}` pair regardless of content: the prose here is
# Markdown, not a template language, but authors legitimately show other
# double-brace-shaped things in running text (e.g. quoting a *different*
# tool's placeholder syntax, or a C-like `{{0}}` initializer in a code
# comment that lives outside a fence). Restricting the net to the word
# "table" keeps the false-positive rate near zero while still catching every
# case this review named, because a mistyped *table* placeholder always
# still mentions "table" -- an author does not typo the word itself, only
# the punctuation around it.
_RESIDUE = re.compile(r"\{\{[^}]*table[^}]*\}\}", re.IGNORECASE)

# Fenced code blocks (``` or ~~~, matched by a backreference so a block
# opened with one marker only closes on the same marker) and inline code
# spans are protected from both placeholder substitution and the residue
# scan below -- this doc's authoring guidance needs to show the
# {{table:...}} syntax literally at least once, inside a code sample, and
# that must not itself be treated as a malformed placeholder.
_PROTECTED = re.compile(
    r"(?P<fence>^(?P<mark>`{3,}|~{3,})[^\n]*\n.*?\n(?P=mark)[ \t]*$)"
    r"|(?P<inline>`[^`\n]+`)",
    re.MULTILINE | re.DOTALL,
)


class UnknownTable(Exception):
    """A {{table:...}} placeholder names something not generated, or is malformed."""


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>"
        for r in rows
    )
    return f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _build_table(kind: str, arg: str | None, gen: dict) -> str:
    if kind == "opcodes":
        cmds = gen["opcodes"]["commands"]
        if arg:
            cmds = [c for c in cmds if c["group"] == arg]
            if not cmds:
                raise UnknownTable(f"no commands in group {arg!r}")
        return _table(
            ["ID", "Name", "Request", "Response", "Notes"],
            [[f"0x{c['id']:02X}", c["name"], c["req"], c["resp"], c["note"]] for c in cmds],
        )
    if kind == "errors":
        return _table(["Code", "Name", "Meaning"],
                      [[f"0x{e['code']:02X}", e["name"], e["note"]]
                       for e in gen["opcodes"]["errors"]])
    if kind == "op_modes":
        return _table(["Value", "Name", "Meaning"],
                      [[f"0x{m['value']:02X}", m["name"], m["note"]]
                       for m in gen["opcodes"]["op_modes"]])
    if kind == "bridge":
        return _table(["ID", "Name", "Notes"],
                      [[f"0x{c['id']:02X}", c["name"], c["note"]]
                       for c in gen["bridge"]["commands"]])
    if kind in ("par", "var"):
        width = arg or ("par16" if kind == "par" else "var8")
        rows_src = gen["varpar"][kind].get(width)
        if rows_src is None:
            raise UnknownTable(f"no {kind} width {width!r}")
        internal = any("default" in r for r in rows_src)
        headers = ["ID", "Name", "Unit"] + (["Access"] if kind == "par" else [])
        if internal:
            headers.append("Default")
        rows = []
        for r in rows_src:
            row = [r["id"], r["name"], r.get("unit", "")]
            if kind == "par":
                row.append(r.get("access", ""))
            if internal:
                row.append(r.get("default", ""))
            rows.append(row)
        return _table(headers, rows)
    raise UnknownTable(f"unknown table kind {kind!r}")


def _map_unprotected(text: str, fn) -> str:
    """Apply fn(chunk) to every part of text that is NOT inside a fenced
    code block or inline code span; protected regions pass through as-is."""
    out = []
    pos = 0
    for m in _PROTECTED.finditer(text):
        out.append(fn(text[pos : m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(fn(text[pos:]))
    return "".join(out)


def expand_tables(md_text: str, gen: dict) -> str:
    def sub(chunk: str) -> str:
        def repl(m: re.Match[str]) -> str:
            return _build_table(m.group(1), m.group(2), gen)

        return _PLACEHOLDER.sub(repl, chunk)

    expanded = _map_unprotected(md_text, sub)

    def check(chunk: str) -> str:
        bad = _RESIDUE.search(chunk)
        if bad:
            raise UnknownTable(
                f"malformed table placeholder {bad.group(0)!r}; "
                "expected exact syntax {{table:<kind>}} or {{table:<kind>:<arg>}}"
            )
        return chunk

    _map_unprotected(expanded, check)
    return expanded


def render_page(lang: str, md_text: str, gen: dict, *, for_print: bool) -> str:
    body = markdown.markdown(
        expand_tables(md_text, gen),
        extensions=["tables", "fenced_code", "toc", "attr_list"],
    )
    tpl = Template((ASSETS / "page.html.j2").read_text(encoding="utf-8"))
    return tpl.render(
        lang=lang,
        font_stack=LANG_FONTS[lang],
        title=LANG_TITLE[lang],
        version=gen["version"]["cmd_set_version"],
        edition=gen["version"]["edition"],
        body=body,
        for_print=for_print,
        css=(ASSETS / "style.css").read_text(encoding="utf-8"),
    )
