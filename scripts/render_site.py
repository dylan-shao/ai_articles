#!/usr/bin/env python3

from __future__ import annotations

import re
from pathlib import Path

import markdown


ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content"
SITE_DIR = ROOT / "site"
NON_ITEM_SECTIONS = {
    "Executive Summary",
    "Selected Items",
    "Top Items",
    "New Terms",
    "Themes",
    "Implications",
    "Recommended Reading Order",
    "What to Ignore",
    "Sources Checked",
    "Note",
}


HTML_SHELL = """<!doctype html>
<html lang="{lang}">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f3efe6;
        --panel: #fffdf7;
        --sidebar: #f7f1e5;
        --ink: #1d232b;
        --muted: #606a78;
        --accent: #9f3f14;
        --accent-soft: #f5e4d8;
        --line: #e3d6bf;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        background:
          radial-gradient(circle at top left, #fff9ef 0%, transparent 35%),
          linear-gradient(180deg, #fbf6ed 0%, var(--bg) 100%);
        color: var(--ink);
      }}
      a {{ color: var(--accent); }}
      .wrap {{
        max-width: 1220px;
        margin: 0 auto;
        padding: 24px 18px 48px;
      }}
      .nav {{
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
        margin-bottom: 18px;
        color: var(--muted);
      }}
      .nav a {{
        text-decoration: none;
        font-weight: 700;
      }}
      .layout {{
        display: grid;
        grid-template-columns: 280px minmax(0, 1fr);
        gap: 18px;
        align-items: start;
      }}
      .sidebar, .panel {{
        border: 1px solid var(--line);
        border-radius: 20px;
        box-shadow: 0 12px 30px rgba(58, 43, 21, 0.06);
      }}
      .sidebar {{
        position: sticky;
        top: 18px;
        padding: 20px;
        background: linear-gradient(180deg, #fbf5ea 0%, var(--sidebar) 100%);
      }}
      .panel {{
        padding: 30px;
        background: var(--panel);
      }}
      .sidebar h2, .sidebar h3 {{
        margin: 0 0 12px;
        line-height: 1.15;
      }}
      .sidebar h2 {{
        font-size: 1.1rem;
      }}
      .sidebar h3 {{
        margin-top: 22px;
        font-size: 0.95rem;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }}
      .sidebar ul {{
        list-style: none;
        padding: 0;
        margin: 0;
      }}
      .sidebar li + li {{
        margin-top: 8px;
      }}
      .sidebar a {{
        display: block;
        text-decoration: none;
        padding: 8px 10px;
        border-radius: 10px;
      }}
      .sidebar a:hover {{
        background: rgba(159, 63, 20, 0.08);
      }}
      .sidebar a.current {{
        background: var(--accent-soft);
        font-weight: 700;
      }}
      .lang-switch {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
      }}
      .lang-switch a {{
        text-align: center;
        border: 1px solid var(--line);
        background: #fffaf2;
      }}
      .meta-note {{
        margin: 14px 0 0;
        color: var(--muted);
        font-size: 0.92rem;
      }}
      .panel h1, .panel h2, .panel h3 {{
        line-height: 1.2;
      }}
      .panel h1 {{
        margin-top: 0;
        font-size: 2rem;
      }}
      .panel h2 {{
        margin-top: 2rem;
        font-size: 1.35rem;
      }}
      .panel ul, .panel ol {{
        padding-left: 1.25rem;
      }}
      .panel code {{
        background: #f4ecdf;
        border-radius: 4px;
        padding: 0.1em 0.3em;
      }}
      .priority-note {{
        margin: -0.2rem 0 1.2rem;
        color: var(--muted);
        font-size: 0.95rem;
      }}
      @media (max-width: 900px) {{
        .layout {{
          grid-template-columns: 1fr;
        }}
        .sidebar {{
          position: static;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="nav">
        <a href="/index.html">Latest</a>
        <a href="/archive.html">Archive</a>
        <a href="/latest.zh.html">中文</a>
        <a href="/latest.en.html">English</a>
      </div>
      <div class="layout">
        <aside class="sidebar">
          {sidebar}
        </aside>
        <main class="panel">
          {body}
        </main>
      </div>
    </div>
  </body>
</html>
"""


def content_entries() -> list[str]:
    dates = []
    for path in sorted(CONTENT_DIR.glob("*.zh.md"), reverse=True):
        if path.name.startswith("latest."):
            continue
        dates.append(path.stem.replace(".zh", ""))
    return dates


def score_tuple(block: list[str]) -> tuple[int, int, int]:
    joined = "\n".join(block)
    match = re.search(
        r"Scores:\s*signal\s*(\d+)/5,\s*novelty\s*(\d+)/5,\s*actionability\s*(\d+)/5",
        joined,
        re.IGNORECASE,
    )
    if not match:
        return (0, 0, 0)
    return tuple(int(value) for value in match.groups())


def sort_selected_items_markdown(text: str) -> str:
    lines = text.splitlines()
    try:
        selected_idx = lines.index("## Selected Items")
    except ValueError:
        return text

    next_section_idx = len(lines)
    item_heading_indices: list[int] = []
    for idx in range(selected_idx + 1, len(lines)):
        if not lines[idx].startswith("## "):
            continue
        heading = lines[idx][3:].strip()
        if heading in NON_ITEM_SECTIONS:
            next_section_idx = idx
            break
        item_heading_indices.append(idx)

    if len(item_heading_indices) < 2:
        return text

    blocks: list[list[str]] = []
    for pos, start in enumerate(item_heading_indices):
        end = item_heading_indices[pos + 1] if pos + 1 < len(item_heading_indices) else next_section_idx
        blocks.append(lines[start:end])

    sorted_blocks = sorted(blocks, key=score_tuple, reverse=True)
    rebuilt = lines[: selected_idx + 1]
    rebuilt.append("")
    for block in sorted_blocks:
        rebuilt.extend(block)
        if block and block[-1] != "":
            rebuilt.append("")
    rebuilt.extend(lines[next_section_idx:])
    return "\n".join(rebuilt).strip() + "\n"


def render_markdown(md_text: str) -> str:
    return markdown.markdown(
        md_text,
        extensions=["extra", "sane_lists", "toc"],
    )


def build_sidebar(current_name: str, lang: str) -> str:
    dates = content_entries()
    latest_link = "latest.zh.html" if lang == "zh" else "latest.en.html"
    archive_items = []
    for date in dates:
        target = f"{date}.{lang}.html"
        css_class = "current" if current_name == target else ""
        archive_items.append(f"<li><a class='{css_class}' href='/{target}'>{date}</a></li>")

    zh_target = current_name.replace(".en.html", ".zh.html") if current_name.endswith(".en.html") else current_name
    en_target = current_name.replace(".zh.html", ".en.html") if current_name.endswith(".zh.html") else current_name
    if current_name == "index.html":
        zh_target = "latest.zh.html"
        en_target = "latest.en.html"

    latest_current = "current" if current_name in {"index.html", latest_link} else ""
    archive_current = "current" if current_name == "archive.html" else ""
    return (
        "<h2>AI Coding Digest</h2>"
        "<div class='lang-switch'>"
        f"<a class=\"{'current' if lang == 'zh' else ''}\" href='/{zh_target}'>中文</a>"
        f"<a class=\"{'current' if lang == 'en' else ''}\" href='/{en_target}'>English</a>"
        "</div>"
        "<h3>Views</h3>"
        "<ul>"
        f"<li><a class='{latest_current}' href='/{latest_link}'>Latest digest</a></li>"
        f"<li><a class='{archive_current}' href='/archive.html'>Archive index</a></li>"
        "</ul>"
        "<h3>History</h3>"
        "<ul>"
        + "".join(archive_items)
        + "</ul>"
        "<p class='meta-note'>Left column keeps every archived day. The main column keeps today's items sorted by score priority.</p>"
    )


def build_archive_index() -> str:
    entries = []
    for date in content_entries():
        entries.append(
            f"<li><a href='/{date}.zh.html'>{date} 中文</a> · <a href='/{date}.en.html'>{date} English</a></li>"
        )
    return (
        "<h1>AI Coding Digest Archive</h1>"
        "<p class='priority-note'>历史日期保留在左栏，这一页提供全部入口索引。</p>"
        "<ul>"
        + "".join(entries)
        + "</ul>"
    )


def render_markdown_page(input_path: Path, output_path: Path, lang: str) -> None:
    sorted_md = sort_selected_items_markdown(input_path.read_text())
    body = render_markdown(sorted_md)
    if "## Selected Items" in sorted_md:
        body = body.replace(
            "<h2 id=\"selected-items\">Selected Items</h2>",
            "<h2 id=\"selected-items\">Selected Items</h2><p class='priority-note'>Items below are automatically sorted by signal, novelty, and actionability.</p>",
        )
    output_path.write_text(
        HTML_SHELL.format(
            title=input_path.stem,
            body=body,
            lang=lang,
            sidebar=build_sidebar(output_path.name, lang),
        )
    )


def main() -> int:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    for md_path in CONTENT_DIR.glob("*.md"):
        html_name = md_path.name.replace(".md", ".html")
        lang = "zh" if md_path.name.endswith(".zh.md") else "en"
        render_markdown_page(md_path, SITE_DIR / html_name, lang)

    latest_zh = SITE_DIR / "latest.zh.html"
    (SITE_DIR / "index.html").write_text(
        HTML_SHELL.format(
            title="latest.zh",
            body=render_markdown(sort_selected_items_markdown((CONTENT_DIR / "latest.zh.md").read_text())),
            lang="zh",
            sidebar=build_sidebar("index.html", "zh"),
        )
    )
    (SITE_DIR / "archive.html").write_text(
        HTML_SHELL.format(
            title="Archive",
            body=build_archive_index(),
            lang="zh",
            sidebar=build_sidebar("archive.html", "zh"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
