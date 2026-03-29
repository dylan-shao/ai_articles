#!/usr/bin/env python3

from __future__ import annotations

import re
import json
from pathlib import Path

import markdown


ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content"
SITE_DIR = ROOT / "site"
HARNESS_LIBRARY_PATH = ROOT / "data" / "collections" / "harness_articles.json"
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
        --font-body: Georgia, "Times New Roman", serif;
        --font-display: Georgia, "Times New Roman", serif;
        --bg: #f3efe6;
        --panel: #fffdf7;
        --sidebar: #f7f1e5;
        --nav: rgba(255, 250, 242, 0.86);
        --ink: #1d232b;
        --muted: #606a78;
        --accent: #9f3f14;
        --accent-soft: #f5e4d8;
        --line: #e3d6bf;
        --shadow: 0 12px 30px rgba(58, 43, 21, 0.06);
        --panel-radius: 20px;
        --chip-bg: #fffaf2;
        --hero-glow: radial-gradient(circle at top left, #fff9ef 0%, transparent 35%);
        --page-gradient: linear-gradient(180deg, #fbf6ed 0%, var(--bg) 100%);
        --sidebar-gradient: linear-gradient(180deg, #fbf5ea 0%, var(--sidebar) 100%);
        --panel-padding: 30px;
        --sidebar-width: 280px;
        --nav-border: 1px solid rgba(227, 214, 191, 0.8);
      }}
      body[data-theme="neo"] {{
        --font-body: "Avenir Next", "Helvetica Neue", Helvetica, sans-serif;
        --font-display: "Avenir Next Condensed", "Arial Narrow", sans-serif;
        --bg: #eef4ff;
        --panel: rgba(255, 255, 255, 0.88);
        --sidebar: rgba(232, 242, 255, 0.92);
        --nav: rgba(249, 252, 255, 0.82);
        --ink: #10233f;
        --muted: #4d6484;
        --accent: #0c63ff;
        --accent-soft: rgba(12, 99, 255, 0.12);
        --line: rgba(115, 154, 220, 0.28);
        --shadow: 0 24px 60px rgba(33, 71, 132, 0.16);
        --panel-radius: 28px;
        --chip-bg: rgba(255, 255, 255, 0.72);
        --hero-glow:
          radial-gradient(circle at 10% 10%, rgba(108, 160, 255, 0.38) 0%, transparent 28%),
          radial-gradient(circle at 92% 14%, rgba(94, 214, 202, 0.22) 0%, transparent 20%);
        --page-gradient: linear-gradient(180deg, #f8fbff 0%, #edf4ff 52%, #e5efff 100%);
        --sidebar-gradient: linear-gradient(180deg, rgba(245, 250, 255, 0.95) 0%, rgba(230, 240, 255, 0.92) 100%);
        --panel-padding: 36px;
        --sidebar-width: 300px;
        --nav-border: 1px solid rgba(115, 154, 220, 0.2);
      }}
      body[data-theme="bulletin"] {{
        --font-body: "Palatino Linotype", "Book Antiqua", Palatino, serif;
        --font-display: "Impact", Haettenschweiler, "Arial Narrow Bold", sans-serif;
        --bg: #efe0c9;
        --panel: #fffaf1;
        --sidebar: #f5e7cf;
        --nav: rgba(255, 247, 232, 0.86);
        --ink: #241810;
        --muted: #70584c;
        --accent: #b43a24;
        --accent-soft: rgba(180, 58, 36, 0.13);
        --line: #d5ba95;
        --shadow: 0 18px 44px rgba(77, 43, 22, 0.12);
        --panel-radius: 16px;
        --chip-bg: #fff3df;
        --hero-glow:
          radial-gradient(circle at top left, rgba(255, 236, 196, 0.85) 0%, transparent 32%),
          linear-gradient(135deg, transparent 0%, transparent 68%, rgba(180, 58, 36, 0.06) 68%, rgba(180, 58, 36, 0.06) 71%, transparent 71%);
        --page-gradient: linear-gradient(180deg, #f6ebd8 0%, #eee0c9 100%);
        --sidebar-gradient: linear-gradient(180deg, #f9edda 0%, #f0dec1 100%);
        --panel-padding: 32px;
        --sidebar-width: 292px;
        --nav-border: 1px solid rgba(122, 83, 56, 0.24);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: var(--font-body);
        background:
          var(--hero-glow),
          var(--page-gradient);
        color: var(--ink);
        transition: background 220ms ease, color 220ms ease;
      }}
      a {{ color: var(--accent); }}
      .wrap {{
        max-width: 1220px;
        margin: 0 auto;
        padding: 24px 18px 48px;
      }}
      .nav {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        flex-wrap: wrap;
        margin-bottom: 18px;
        color: var(--muted);
        padding: 14px 16px;
        border: var(--nav-border);
        border-radius: calc(var(--panel-radius) - 2px);
        background: var(--nav);
        backdrop-filter: blur(18px);
        box-shadow: var(--shadow);
      }}
      .nav-links, .theme-switch {{
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        align-items: center;
      }}
      .nav a, .theme-switch button {{
        text-decoration: none;
        font-weight: 700;
        color: var(--ink);
        border: 1px solid transparent;
        background: transparent;
        border-radius: 999px;
        padding: 10px 14px;
        cursor: pointer;
        font: inherit;
        transition: transform 160ms ease, background 160ms ease, border-color 160ms ease, color 160ms ease;
      }}
      .nav a:hover, .theme-switch button:hover {{
        transform: translateY(-1px);
        background: var(--chip-bg);
        border-color: var(--line);
      }}
      .theme-switch button.active {{
        background: var(--accent);
        color: #fff;
        border-color: var(--accent);
      }}
      .layout {{
        display: grid;
        grid-template-columns: var(--sidebar-width) minmax(0, 1fr);
        gap: 18px;
        align-items: start;
      }}
      .sidebar, .panel {{
        border: 1px solid var(--line);
        border-radius: var(--panel-radius);
        box-shadow: var(--shadow);
      }}
      .sidebar {{
        position: sticky;
        top: 18px;
        padding: 20px;
        background: var(--sidebar-gradient);
      }}
      .panel {{
        padding: var(--panel-padding);
        background: var(--panel);
      }}
      .sidebar h2, .sidebar h3 {{
        margin: 0 0 12px;
        line-height: 1.15;
      }}
      .sidebar h2 {{
        font-size: 1.1rem;
        font-family: var(--font-display);
        letter-spacing: 0.02em;
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
        background: var(--chip-bg);
      }}
      .meta-note {{
        margin: 14px 0 0;
        color: var(--muted);
        font-size: 0.92rem;
      }}
      .panel h1, .panel h2, .panel h3 {{
        line-height: 1.2;
        font-family: var(--font-display);
      }}
      .panel h1 {{
        margin-top: 0;
        font-size: clamp(2.2rem, 3.6vw, 3.4rem);
        letter-spacing: 0.02em;
      }}
      .panel h2 {{
        margin-top: 2rem;
        font-size: 1.35rem;
      }}
      .panel ul, .panel ol {{
        padding-left: 1.25rem;
      }}
      .panel code {{
        background: var(--chip-bg);
        border-radius: 4px;
        padding: 0.1em 0.3em;
      }}
      .panel p, .panel li {{
        font-size: 1.02rem;
        line-height: 1.72;
      }}
      .panel p {{
        margin: 0.9rem 0 1rem;
      }}
      .panel h2[id="selected-items"] {{
        padding-top: 0.4rem;
        border-top: 1px solid var(--line);
      }}
      .priority-note {{
        margin: -0.2rem 0 1.2rem;
        color: var(--muted);
        font-size: 0.95rem;
      }}
      .theme-note {{
        margin-top: 18px;
        padding: 12px 14px;
        border: 1px dashed var(--line);
        border-radius: 14px;
        background: var(--chip-bg);
        color: var(--muted);
        font-size: 0.92rem;
      }}
      body[data-theme="neo"] .panel {{
        backdrop-filter: blur(16px);
      }}
      body[data-theme="neo"] .panel h2 {{
        display: inline-block;
        padding: 0.2rem 0.8rem 0.28rem;
        border-radius: 999px;
        background: rgba(12, 99, 255, 0.08);
      }}
      body[data-theme="neo"] .sidebar a.current {{
        box-shadow: inset 0 0 0 1px rgba(12, 99, 255, 0.14);
      }}
      body[data-theme="bulletin"] .panel {{
        position: relative;
      }}
      body[data-theme="bulletin"] .panel::before {{
        content: "FIELD REPORT";
        display: inline-block;
        margin-bottom: 1rem;
        padding: 0.3rem 0.55rem;
        border: 1px solid var(--accent);
        color: var(--accent);
        font: 700 0.78rem/1 var(--font-display);
        letter-spacing: 0.14em;
      }}
      body[data-theme="bulletin"] .panel h1 {{
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }}
      body[data-theme="bulletin"] .panel h2 {{
        border-bottom: 2px solid var(--line);
        padding-bottom: 0.35rem;
      }}
      @media (max-width: 900px) {{
        .layout {{
          grid-template-columns: 1fr;
        }}
        .sidebar {{
          position: static;
        }}
        .nav {{
          padding: 12px;
        }}
        .nav-links, .theme-switch {{
          width: 100%;
        }}
      }}
    </style>
  </head>
  <body data-theme="classic">
    <div class="wrap">
      <div class="nav">
        <div class="nav-links">
          <a href="index.html">Latest</a>
          <a href="archive.html">Archive</a>
          <a href="harness.html">Harness Library</a>
          <a href="latest.zh.html">中文</a>
          <a href="latest.en.html">English</a>
        </div>
        <div class="theme-switch" aria-label="Theme switcher">
          <button type="button" data-theme-option="classic">Classic</button>
          <button type="button" data-theme-option="neo">Neo</button>
          <button type="button" data-theme-option="bulletin">Bulletin</button>
        </div>
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
    <script>
      (function () {{
        var key = "ai-digest-theme";
        var allowed = ["classic", "neo", "bulletin"];
        var body = document.body;
        var buttons = Array.prototype.slice.call(document.querySelectorAll("[data-theme-option]"));

        function setTheme(theme) {{
          var nextTheme = allowed.indexOf(theme) >= 0 ? theme : "classic";
          body.setAttribute("data-theme", nextTheme);
          buttons.forEach(function (button) {{
            button.classList.toggle("active", button.getAttribute("data-theme-option") === nextTheme);
          }});
          try {{
            window.localStorage.setItem(key, nextTheme);
          }} catch (err) {{
          }}
        }}

        var initialTheme = "classic";
        try {{
          var stored = window.localStorage.getItem(key);
          if (stored && allowed.indexOf(stored) >= 0) {{
            initialTheme = stored;
          }}
        }} catch (err) {{
        }}

        buttons.forEach(function (button) {{
          button.addEventListener("click", function () {{
            setTheme(button.getAttribute("data-theme-option"));
          }});
        }});

        setTheme(initialTheme);
      }})();
    </script>
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


def load_harness_items() -> list[dict]:
    if not HARNESS_LIBRARY_PATH.exists():
        return []
    payload = json.loads(HARNESS_LIBRARY_PATH.read_text())
    return sorted(payload.get("items", []), key=lambda entry: entry.get("published_date", ""), reverse=True)


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
    md_text = re.sub(
        r"(^-\s+URL:\s+)(https?://\S+)$",
        r"\1[\2](\2)",
        md_text,
        flags=re.MULTILINE,
    )
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
        archive_items.append(f"<li><a class='{css_class}' href='{target}'>{date}</a></li>")

    zh_target = current_name.replace(".en.html", ".zh.html") if current_name.endswith(".en.html") else current_name
    en_target = current_name.replace(".zh.html", ".en.html") if current_name.endswith(".zh.html") else current_name
    if current_name == "index.html":
        zh_target = "latest.zh.html"
        en_target = "latest.en.html"

    latest_current = "current" if current_name in {"index.html", latest_link} else ""
    archive_current = "current" if current_name == "archive.html" else ""
    harness_current = "current" if current_name == "harness.html" else ""
    return (
        "<h2>AI Coding Digest</h2>"
        "<div class='lang-switch'>"
        f"<a class=\"{'current' if lang == 'zh' else ''}\" href='{zh_target}'>中文</a>"
        f"<a class=\"{'current' if lang == 'en' else ''}\" href='{en_target}'>English</a>"
        "</div>"
        "<h3>Views</h3>"
        "<ul>"
        f"<li><a class='{latest_current}' href='{latest_link}'>Latest digest</a></li>"
        f"<li><a class='{archive_current}' href='archive.html'>Archive index</a></li>"
        f"<li><a class='{harness_current}' href='harness.html'>Harness library</a></li>"
        "</ul>"
        "<h3>History</h3>"
        "<ul>"
        + "".join(archive_items)
        + "</ul>"
        "<p class='meta-note'>Left column keeps every archived day. The main column keeps today's items sorted by score priority.</p>"
        "<div class='theme-note'>Theme switcher keeps the classic layout and adds two alternate views. Your choice is remembered on this device.</div>"
    )


def build_archive_index() -> str:
    entries = []
    for date in content_entries():
        entries.append(
            f"<li><a href='{date}.zh.html'>{date} 中文</a> · <a href='{date}.en.html'>{date} English</a></li>"
        )
    return (
        "<h1>AI Coding Digest Archive</h1>"
        "<p class='priority-note'>历史日期保留在左栏，这一页提供全部入口索引。</p>"
        "<ul>"
        + "".join(entries)
        + "</ul>"
    )


def build_harness_page() -> str:
    items = load_harness_items()
    cards = []
    for item in items:
        cards.append(
            "<article style='border:1px solid var(--line); border-radius:16px; padding:18px; margin:0 0 16px; background:#fffaf2;'>"
            f"<h2 style='margin-top:0;'><a href='{item['url']}' target='_blank' rel='noopener noreferrer'>{item['title']}</a></h2>"
            f"<p style='margin:0 0 8px; color:var(--muted);'>{item.get('published_date', 'Unknown')} · {item.get('source', 'Unknown source')}</p>"
            f"<p style='margin:0 0 10px;'><strong>核心总结：</strong>{item.get('summary', '')}</p>"
            f"<p style='margin:0;'><strong>链接：</strong><a href='{item['url']}' target='_blank' rel='noopener noreferrer'>{item['url']}</a></p>"
            "</article>"
        )
    intro = (
        "<h1>Harness Engineering Library</h1>"
        "<p class='priority-note'>这一页汇总 harness engineering 相关的经典文章、最佳实践和高质量工程总结。首批内容来自历史高质量文章的人工 seed，后续每天 digest 命中相关条目时会自动补充进来。</p>"
    )
    return intro + "".join(cards)


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
    (SITE_DIR / "harness.html").write_text(
        HTML_SHELL.format(
            title="Harness Library",
            body=build_harness_page(),
            lang="zh",
            sidebar=build_sidebar("harness.html", "zh"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
