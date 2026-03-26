#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

import markdown


ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content"
SITE_DIR = ROOT / "site"


HTML_SHELL = """<!doctype html>
<html lang="{lang}">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f7f4ec;
        --panel: #fffdf8;
        --ink: #1f2328;
        --muted: #55606e;
        --accent: #9c3d10;
        --line: #e6dcc9;
      }}
      body {{
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        background: radial-gradient(circle at top, #fffaf0 0%, var(--bg) 65%);
        color: var(--ink);
      }}
      .wrap {{
        max-width: 880px;
        margin: 0 auto;
        padding: 32px 20px 64px;
      }}
      .panel {{
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 28px;
        box-shadow: 0 10px 30px rgba(55, 43, 22, 0.06);
      }}
      a {{ color: var(--accent); }}
      .nav {{
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
        margin-bottom: 20px;
        color: var(--muted);
      }}
      .nav a {{
        text-decoration: none;
        font-weight: 600;
      }}
      h1, h2, h3 {{ line-height: 1.2; }}
      ul, ol {{ padding-left: 1.25rem; }}
      code {{
        background: #f4ecdf;
        border-radius: 4px;
        padding: 0.1em 0.3em;
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
      <div class="panel">
        {body}
      </div>
    </div>
  </body>
</html>
"""


def render_markdown_page(input_path: Path, output_path: Path, title: str, lang: str) -> None:
    body = markdown.markdown(
        input_path.read_text(),
        extensions=["extra", "sane_lists", "toc"],
    )
    output_path.write_text(HTML_SHELL.format(title=title, body=body, lang=lang))


def build_archive_index() -> str:
    entries = []
    for path in sorted(CONTENT_DIR.glob("*.zh.md"), reverse=True):
        if path.name.startswith("latest."):
            continue
        date = path.stem.replace(".zh", "")
        entries.append(
            f"<li><a href='/{date}.zh.html'>{date} 中文</a> · <a href='/{date}.en.html'>{date} English</a></li>"
        )
    return (
        "<h1>AI Coding Digest Archive</h1>"
        "<p>Daily digests generated from the GitHub Actions pipeline.</p>"
        "<ul>"
        + "".join(entries)
        + "</ul>"
    )


def main() -> int:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    for md_path in CONTENT_DIR.glob("*.md"):
        html_name = md_path.name.replace(".md", ".html")
        lang = "zh" if md_path.name.endswith(".zh.md") else "en"
        render_markdown_page(md_path, SITE_DIR / html_name, md_path.stem, lang)

    (SITE_DIR / "index.html").write_text((SITE_DIR / "latest.zh.html").read_text())
    (SITE_DIR / "archive.html").write_text(
        HTML_SHELL.format(title="Archive", body=build_archive_index(), lang="en")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
