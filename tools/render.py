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


class UnknownTable(Exception):
    """A {{table:...}} placeholder names something not generated."""


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


def expand_tables(md_text: str, gen: dict) -> str:
    def sub(m: re.Match[str]) -> str:
        return _build_table(m.group(1), m.group(2), gen)

    return _PLACEHOLDER.sub(sub, md_text)


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
