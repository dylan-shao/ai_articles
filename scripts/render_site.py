#!/usr/bin/env python3

from __future__ import annotations

import re
import json
from pathlib import Path

import markdown
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content"
SITE_DIR = ROOT / "site"
DATA_PROCESSED_DIR = ROOT / "data" / "processed"
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
      .video-icon-link {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.75rem;
        height: 1.75rem;
        margin-left: 0.45rem;
        border-radius: 999px;
        background: #ff0033;
        color: #fff !important;
        text-decoration: none;
        vertical-align: middle;
        box-shadow: 0 8px 18px rgba(255, 0, 51, 0.18);
      }}
      .video-icon-link:hover {{
        transform: translateY(-1px);
        filter: brightness(1.03);
      }}
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
      body.page-video .wrap {{
        max-width: min(1680px, 100vw);
      }}
      body.page-video .layout {{
        grid-template-columns: 1fr;
      }}
      body.page-video .sidebar {{
        display: none;
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
      .video-detail {{
        display: grid;
        grid-template-columns: minmax(280px, 3fr) minmax(0, 7fr);
        gap: 22px;
        align-items: start;
      }}
      .video-player-card, .video-summary-card {{
        border: 1px solid var(--line);
        border-radius: 18px;
        background: var(--chip-bg);
        padding: 18px;
      }}
      body.page-video .panel {{
        padding: 22px;
      }}
      body.page-video .video-player-card,
      body.page-video .video-summary-card {{
        min-height: calc(100vh - 160px);
      }}
      .video-embed {{
        width: 100%;
        height: min(70vh, 860px);
        border: 0;
        border-radius: 14px;
        background: #000;
      }}
      .video-fallback {{
        position: relative;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        width: 100%;
        height: min(70vh, 860px);
        border-radius: 18px;
        padding: 28px;
        color: #fff;
        background:
          linear-gradient(180deg, rgba(10, 15, 25, 0.12) 0%, rgba(10, 15, 25, 0.9) 100%),
          linear-gradient(135deg, #8f1d13 0%, #c33b1f 38%, #1f2735 100%);
        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08);
        overflow: hidden;
      }}
      .video-fallback::before {{
        content: "";
        position: absolute;
        inset: 0;
        background:
          linear-gradient(180deg, rgba(10, 15, 25, 0.08) 0%, rgba(10, 15, 25, 0.88) 100%),
          var(--video-poster, none);
        background-size: cover;
        background-position: center;
        transform: scale(1.02);
        pointer-events: none;
      }}
      .video-fallback-content {{
        position: relative;
        z-index: 1;
      }}
      .video-fallback-kicker {{
        display: inline-flex;
        width: fit-content;
        margin-bottom: 14px;
        padding: 0.4rem 0.7rem;
        border-radius: 999px;
        background: rgba(255,255,255,0.14);
        font-size: 0.82rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
      }}
      .video-fallback h2 {{
        margin: 0 0 10px;
        font-size: clamp(2rem, 3vw, 3.4rem);
        color: #fff;
      }}
      .video-fallback p {{
        max-width: 42rem;
        margin: 0 0 18px;
        color: rgba(255,255,255,0.88);
      }}
      .video-play-button {{
        position: absolute;
        top: 22px;
        right: 22px;
        z-index: 2;
        display: inline-flex;
        align-items: center;
        gap: 10px;
        border: 0;
        border-radius: 999px;
        padding: 12px 18px;
        background: rgba(255,255,255,0.92);
        color: #111827;
        font: inherit;
        font-weight: 700;
        cursor: pointer;
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.22);
      }}
      .video-play-button:hover {{
        transform: translateY(-1px);
      }}
      .video-actions {{
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
      }}
      .video-action {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 180px;
        padding: 12px 18px;
        border-radius: 999px;
        text-decoration: none;
        font-weight: 700;
      }}
      .video-action-primary {{
        background: #fff;
        color: #111827 !important;
      }}
      .video-action-secondary {{
        background: rgba(255,255,255,0.12);
        color: #fff !important;
        border: 1px solid rgba(255,255,255,0.18);
      }}
      .video-summary-card h2 {{
        margin-top: 0;
      }}
      .video-overview {{
        margin-bottom: 18px;
        color: var(--ink);
      }}
      .video-highlights {{
        display: grid;
        gap: 12px;
      }}
      .video-highlight {{
        width: 100%;
        text-align: left;
        border: 1px solid var(--line);
        border-radius: 14px;
        background: var(--panel);
        color: var(--ink);
        padding: 14px 16px;
        cursor: pointer;
      }}
      .video-highlight:hover {{
        border-color: var(--accent);
        background: var(--accent-soft);
      }}
      .video-timecode {{
        display: inline-block;
        margin-bottom: 6px;
        font-weight: 700;
        color: var(--accent);
      }}
      .video-source-link {{
        margin-top: 12px;
        font-size: 0.95rem;
        color: var(--muted);
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
        .video-detail {{
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
  <body class="{body_class}" data-theme="classic">
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

        Array.prototype.slice.call(document.querySelectorAll("[data-jump-to]")).forEach(function (button) {{
          button.addEventListener("click", function () {{
            var jumpUrl = button.getAttribute("data-jump-url");
            if (jumpUrl) {{
              window.open(jumpUrl, "_blank", "noopener,noreferrer");
              return;
            }}
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


def load_processed_items() -> list[dict]:
    items: list[dict] = []
    for path in sorted(DATA_PROCESSED_DIR.glob("*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        for item in payload.get("items", []):
            if item.get("video", {}).get("slug"):
                items.append(item)
    return items


def load_all_video_items() -> list[dict]:
    items = load_processed_items()
    for item in load_harness_items():
        if item.get("video", {}).get("slug"):
            items.append(item)
    return items


def render_video_icon(item: dict, lang: str) -> str:
    video = item.get("video")
    if not video or not video.get("slug"):
        return ""
    label = "查看视频总结" if lang == "zh" else "Open video summary"
    return (
        f"<a class='video-icon-link' href='video-{video['slug']}.{lang}.html' "
        f"title='{label}' aria-label='{label}'>"
        "<span aria-hidden='true'>▶</span>"
        "</a>"
    )


def build_video_pages() -> list[tuple[str, str, str]]:
    pages: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in load_all_video_items():
        video = item.get("video", {})
        slug = video.get("slug")
        if not slug:
            continue
        for lang in ["zh", "en"]:
            key = (slug, lang)
            if key in seen:
                continue
            seen.add(key)
            pages.append((f"video-{slug}.{lang}.html", build_video_page(item, lang), lang))
    return pages


def load_processed_payload_for_markdown(input_path: Path) -> dict:
    if input_path.name.startswith("latest."):
        candidates = sorted(DATA_PROCESSED_DIR.glob("*.json"), reverse=True)
        if not candidates:
            return {}
        return json.loads(candidates[0].read_text())
    date = input_path.stem.split(".")[0]
    path = DATA_PROCESSED_DIR / f"{date}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def inject_video_icons(body: str, input_path: Path, lang: str) -> str:
    payload = load_processed_payload_for_markdown(input_path)
    items_by_title = {
        item.get("title", ""): item for item in payload.get("items", []) if item.get("video", {}).get("slug")
    }
    if not items_by_title:
        return body
    soup = BeautifulSoup(body, "html.parser")
    for heading in soup.find_all("h2"):
        title = heading.get_text(" ", strip=True)
        item = items_by_title.get(title)
        if not item or heading.find(class_="video-icon-link"):
            continue
        icon = BeautifulSoup(render_video_icon(item, lang), "html.parser")
        heading.append(icon)
    return str(soup)


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


def build_video_page(item: dict, lang: str) -> str:
    suffix = "zh" if lang == "zh" else "en"
    video = item.get("video", {})
    overview = video.get(f"overview_{suffix}", "")
    basis_note = video.get(f"summary_basis_{suffix}", "")
    highlights_html = []
    for highlight in video.get("highlights", []):
        title = highlight.get(f"title_{suffix}", "")
        summary = highlight.get(f"summary_{suffix}", "")
        jump_url = f"{video.get('youtube_url', '')}&t={highlight.get('start_seconds', 0)}s"
        highlights_html.append(
            "<button class='video-highlight' type='button' "
            f"data-jump-to='{highlight.get('start_seconds', 0)}' "
            f"data-jump-url='{jump_url}'>"
            f"<span class='video-timecode'>{highlight.get('timecode', '0:00')}</span>"
            f"<strong>{title}</strong>"
            f"<p>{summary}</p>"
            "</button>"
        )
    article_label = "原文链接" if lang == "zh" else "Article link"
    video_label = "YouTube 链接" if lang == "zh" else "YouTube link"
    page_title = item.get("title", "Video summary")
    open_label = "在 YouTube 中打开视频" if lang == "zh" else "Open on YouTube"
    article_open_label = "查看原文" if lang == "zh" else "Open article"
    play_label = "在页面内播放" if lang == "zh" else "Play in page"
    play_hint = (
        "由于当前视频在页面内嵌播放不稳定，这里改为稳定方案：保留封面和结构化重点，播放统一跳转到 YouTube。"
        if lang == "zh"
        else "Inline playback is unreliable for this video in the current environment, so this page keeps the poster and structured highlights while opening playback on YouTube."
    )
    poster_url = f"https://i.ytimg.com/vi/{video.get('video_id', '')}/maxresdefault.jpg"
    return (
        f"<h1>{page_title}</h1>"
        "<p class='priority-note'>"
        + (
            basis_note
            or (
                "左侧是原始视频，右侧是基于完整 transcript 生成的结构化摘要；点击任一片段会让视频从对应时间开始播放。"
                if lang == "zh"
                else "The player stays on the left and the transcript-based summary stays on the right. Click any highlight to jump the video to that moment."
            )
        )
        + "</p>"
        "<div class='video-detail'>"
        "<section class='video-player-card'>"
        f"<div class='video-fallback' style=\"--video-poster:url('{poster_url}');\">"
        f"<a class='video-play-button' href='{video.get('youtube_url', '')}' target='_blank' rel='noopener noreferrer'><span aria-hidden='true'>▶</span>{play_label}</a>"
        "<div class='video-fallback-content'>"
        f"<span class='video-fallback-kicker'>{'YouTube Companion' if lang == 'en' else 'YouTube 伴随页'}</span>"
        f"<h2>{page_title}</h2>"
        + (
            f"<p>{play_hint}</p>"
            if lang == "en"
            else f"<p>{play_hint}</p>"
        )
        + "<div class='video-actions'>"
        + f"<a class='video-action video-action-primary' href='{video.get('youtube_url', '')}' target='_blank' rel='noopener noreferrer'>{open_label}</a>"
        + f"<a class='video-action video-action-secondary' href='{item.get('url', '')}' target='_blank' rel='noopener noreferrer'>{article_open_label}</a>"
        + "</div>"
        + "</div>"
        + "</div>"
        f"<p class='video-source-link'>{article_label}: <a href='{item.get('url', '')}' target='_blank' rel='noopener noreferrer'>{item.get('url', '')}</a><br />"
        f"{video_label}: <a href='{video.get('youtube_url', '')}' target='_blank' rel='noopener noreferrer'>{video.get('youtube_url', '')}</a></p>"
        "</section>"
        "<section class='video-summary-card'>"
        + (f"<h2>{'视频总结' if lang == 'zh' else 'Video summary'}</h2>" if overview else "")
        + (f"<p class='video-overview'>{overview}</p>" if overview else "")
        + f"<div class='video-highlights'>{''.join(highlights_html)}</div>"
        "</section>"
        "</div>"
    )


def build_harness_page() -> str:
    items = load_harness_items()
    cards = []
    for item in items:
        icon = render_video_icon(item, "zh")
        cards.append(
            "<article style='border:1px solid var(--line); border-radius:16px; padding:18px; margin:0 0 16px; background:#fffaf2;'>"
            f"<h2 style='margin-top:0;'><a href='{item['url']}' target='_blank' rel='noopener noreferrer'>{item['title']}</a>{icon}</h2>"
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
    body = inject_video_icons(body, input_path, lang)
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
            body_class="",
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
            body=inject_video_icons(
                render_markdown(sort_selected_items_markdown((CONTENT_DIR / "latest.zh.md").read_text())),
                CONTENT_DIR / "latest.zh.md",
                "zh",
            ),
            lang="zh",
            sidebar=build_sidebar("index.html", "zh"),
            body_class="",
        )
    )
    (SITE_DIR / "archive.html").write_text(
        HTML_SHELL.format(
            title="Archive",
            body=build_archive_index(),
            lang="zh",
            sidebar=build_sidebar("archive.html", "zh"),
            body_class="",
        )
    )
    (SITE_DIR / "harness.html").write_text(
        HTML_SHELL.format(
            title="Harness Library",
            body=build_harness_page(),
            lang="zh",
            sidebar=build_sidebar("harness.html", "zh"),
            body_class="",
        )
    )
    for html_name, body, lang in build_video_pages():
        (SITE_DIR / html_name).write_text(
            HTML_SHELL.format(
                title=html_name.replace(".html", ""),
                body=body,
                lang=lang,
                sidebar=build_sidebar(html_name, lang),
                body_class="page-video",
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
