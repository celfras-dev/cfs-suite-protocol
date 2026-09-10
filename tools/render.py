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

# {{table:<kind>}}, {{table:<kind>:<arg>}}, and now also
# {{table:<kind>:<arg>:no_notes}} -- an explicit call-site suffix that drops
# a generated table's Notes/Meaning column. For a kind that takes no real
# <arg> (op_modes, errors, ver_selectors, log_fields, bridge), "no_notes"
# is written in the <arg> slot itself: {{table:op_modes:no_notes}}. Both
# forms are normalized by _consume_no_notes() below. This exists because
# generated tables are for identifiers and values, which must never go
# stale; a note column carries firmware-comment prose (FSM state names,
# driver function names, argument names) that is a convenience for firmware
# developers, not normative standard text -- see PLATFORM_HANDOFF-adjacent
# review that found OPMODE_ISP's and CMD_RESET's notes leaking exactly that
# into the neutral half of the document. Dropping the column at an explicit
# call site is honest; guessing which words are product-internal is not.
_PLACEHOLDER = re.compile(
    r"\{\{table:([a-z_]+)(?::([a-z_0-9]+))?(?::([a-z_0-9]+))?\}\}"
)

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


def _consume_no_notes(arg: str | None, modifier: str | None) -> tuple[str | None, bool]:
    """Normalize the "no_notes" modifier regardless of which placeholder
    segment it arrived in.

    A kind that also takes a real <arg> gets it as the third segment
    ({{table:opcodes:core:no_notes}}); a kind with no <arg> of its own gets
    it as the second ({{table:op_modes:no_notes}}), since that slot would
    otherwise be unused. Either way this returns the *real* arg (None if
    there wasn't one) plus a no_notes flag, so every branch in
    _build_table() only has to check one thing. Anything in the modifier
    slot other than "no_notes" is a call-site typo, not silent text.
    """
    if modifier is not None:
        if modifier != "no_notes":
            raise UnknownTable(f"unknown table modifier {modifier!r}")
        return arg, True
    if arg == "no_notes":
        return None, True
    return arg, False


def _build_table(kind: str, arg: str | None, modifier: str | None, gen: dict) -> str:
    if kind == "opcodes":
        arg, no_notes = _consume_no_notes(arg, modifier)
        cmds = gen["opcodes"]["commands"]
        if arg:
            cmds = [c for c in cmds if c["group"] == arg]
            if not cmds:
                raise UnknownTable(f"no commands in group {arg!r}")
        headers = ["ID", "Name", "Request", "Response"] + ([] if no_notes else ["Notes"])
        rows = []
        for c in cmds:
            row = [f"0x{c['id']:02X}", c["name"], c["req"], c["resp"]]
            if not no_notes:
                row.append(c["note"])
            rows.append(row)
        return _table(headers, rows)
    if kind in ("errors", "op_modes", "ver_selectors", "log_fields"):
        arg, no_notes = _consume_no_notes(arg, modifier)
        if arg is not None:
            raise UnknownTable(f"{kind} takes no argument (got {arg!r})")
        key, id_fmt, items = {
            "errors": ("code", "0x{:02X}", gen["opcodes"]["errors"]),
            "op_modes": ("value", "0x{:02X}", gen["opcodes"]["op_modes"]),
            "ver_selectors": ("value", "0x{:02X}", gen["opcodes"]["ver_selectors"]),
            "log_fields": ("bit", "0x{:02X}", gen["opcodes"]["log_fields"]),
        }[kind]
        id_header = {"code": "Code", "value": "Value", "bit": "Bit"}[key]
        headers = [id_header, "Name"] + ([] if no_notes else ["Meaning"])
        rows = []
        for it in items:
            row = [id_fmt.format(it[key]), it["name"]]
            if not no_notes:
                row.append(it["note"])
            rows.append(row)
        return _table(headers, rows)
    if kind == "bridge":
        arg, no_notes = _consume_no_notes(arg, modifier)
        if arg is not None:
            raise UnknownTable(f"bridge takes no argument (got {arg!r})")
        headers = ["ID", "Name"] + ([] if no_notes else ["Notes"])
        rows = []
        for c in gen["bridge"]["commands"]:
            row = [f"0x{c['id']:02X}", c["name"]]
            if not no_notes:
                row.append(c["note"])
            rows.append(row)
        return _table(headers, rows)
    if kind == "burst_limits":
        # No note column exists here at all (BURST_* constants carry no
        # same-line comments in app_proto.h), so no_notes is accepted for
        # symmetry with the other kinds but has nothing to drop.
        arg, _no_notes = _consume_no_notes(arg, modifier)
        if arg is not None:
            raise UnknownTable(f"burst_limits takes no argument (got {arg!r})")
        return _table(["Name", "Value"],
                      [[b["name"], b["value"]] for b in gen["opcodes"]["burst_limits"]])
    if kind in ("par", "var"):
        arg, _no_notes = _consume_no_notes(arg, modifier)
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
            return _build_table(m.group(1), m.group(2), m.group(3), gen)

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
