#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "sources.json"
CONTENT_DIR = ROOT / "content"
DATA_RAW_DIR = ROOT / "data" / "raw"
DATA_PROCESSED_DIR = ROOT / "data" / "processed"
DEFAULT_TIMEOUT = 20
MAX_LINKS_PER_SOURCE = 16
MIN_KEYWORD_HITS = 2
KEYWORDS = [
    "ai coding",
    "coding agent",
    "coding agents",
    "agentic software engineering",
    "agentic coding",
    "software engineering",
    "swe-bench",
    "repo-scale",
    "terminal-bench",
    "context engineering",
    "mcp",
    "code review automation",
    "eval",
    "evaluations",
    "benchmark",
    "developer tooling",
    "cli",
    "ide",
    "tool use",
]

SYSTEM_PROMPT = """You are an AI coding daily intelligence analyst.
Return valid JSON only.
Select the highest-signal items from the candidate list for an experienced backend/platform/engineering lead.
Prioritize original technical sources about AI coding agents, coding evals, harness design, MCP, repo understanding, developer tooling, and organizational adoption of AI coding.
Exclude generic AI news, fundraising, partnerships, shallow launches, reposts, or opinion pieces without technical insight.
Prefer 2-8 items. If the day is weak, return only the strong items.
If no item is strong enough, set `full_digest_worthy` to false and keep at most 3 borderline items.
"""


@dataclass
class Candidate:
    title: str
    source: str
    url: str
    landing_url: str
    priority: int
    publish_date: str | None
    author: str | None
    excerpt: str
    body_excerpt: str
    keyword_hits: int


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_sources() -> list[dict]:
    return json.loads(CONFIG_PATH.read_text())


def slug_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def ensure_dirs() -> None:
    for directory in [CONTENT_DIR, DATA_RAW_DIR, DATA_PROCESSED_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def count_keyword_hits(text: str) -> int:
    haystack = text.lower()
    return sum(1 for keyword in KEYWORDS if keyword in haystack)


def allowed_link(url: str, source: dict) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc not in source["allowed_domains"]:
        return False
    return any(parsed.path.startswith(prefix) for prefix in source["allowed_path_prefixes"])


def parse_publish_date(soup: BeautifulSoup, html: str) -> datetime | None:
    selectors = [
        ("meta", {"property": "article:published_time"}, "content"),
        ("meta", {"name": "article:published_time"}, "content"),
        ("meta", {"property": "og:published_time"}, "content"),
        ("meta", {"name": "pubdate"}, "content"),
        ("time", {"datetime": True}, "datetime"),
    ]
    for tag_name, attrs, field in selectors:
        tag = soup.find(tag_name, attrs=attrs)
        if tag and tag.get(field):
            parsed = try_parse_datetime(tag.get(field))
            if parsed:
                return parsed

    ld_match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
    if ld_match:
        parsed = try_parse_datetime(ld_match.group(1))
        if parsed:
            return parsed

    text = clean_text(soup.get_text(" ", strip=True))
    date_patterns = [
        r"([A-Z][a-z]{2,8} \d{1,2}, \d{4})",
        r"(\d{4}-\d{2}-\d{2})",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            parsed = try_parse_datetime(match.group(1))
            if parsed:
                return parsed
    return None


def try_parse_datetime(value: str) -> datetime | None:
    value = value.strip()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def fetch(session: requests.Session, url: str) -> requests.Response:
    response = session.get(
        url,
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": "ai-coding-digest-bot/1.0"},
    )
    response.raise_for_status()
    return response


def extract_links(session: requests.Session, source: dict) -> list[str]:
    html = fetch(session, source["landing_url"]).text
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin(source["landing_url"], anchor["href"])
        href = href.split("#", 1)[0]
        if href in seen or not allowed_link(href, source):
            continue
        label = clean_text(anchor.get_text(" ", strip=True))
        if len(label) < 8:
            continue
        seen.add(href)
        links.append(href)
        if len(links) >= MAX_LINKS_PER_SOURCE:
            break
    return links


def extract_candidate(session: requests.Session, source: dict, article_url: str, since: datetime) -> Candidate | None:
    html = fetch(session, article_url).text
    soup = BeautifulSoup(html, "html.parser")
    title = clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    if not title:
        h1 = soup.find("h1")
        title = clean_text(h1.get_text(" ", strip=True)) if h1 else article_url

    description_tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    excerpt = clean_text(description_tag.get("content", "") if description_tag else "")
    article_text = clean_text(soup.get_text(" ", strip=True))
    body_excerpt = article_text[:2000]
    keyword_hits = count_keyword_hits(" ".join([title, excerpt, body_excerpt]))
    if keyword_hits < MIN_KEYWORD_HITS:
        return None

    publish_dt = parse_publish_date(soup, html)
    if publish_dt and publish_dt < since:
        return None

    author = None
    author_meta = soup.find("meta", attrs={"name": "author"}) or soup.find("meta", attrs={"property": "author"})
    if author_meta and author_meta.get("content"):
        author = clean_text(author_meta["content"])

    return Candidate(
        title=title,
        source=source["name"],
        url=article_url,
        landing_url=source["landing_url"],
        priority=source["priority"],
        publish_date=publish_dt.isoformat() if publish_dt else None,
        author=author,
        excerpt=excerpt,
        body_excerpt=body_excerpt,
        keyword_hits=keyword_hits,
    )


def collect_candidates(now: datetime) -> list[Candidate]:
    since = now - timedelta(hours=30)
    session = requests.Session()
    candidates: list[Candidate] = []
    for source in load_sources():
        try:
            links = extract_links(session, source)
        except requests.RequestException as exc:
            print(f"[warn] failed to read {source['name']}: {exc}", file=sys.stderr)
            continue
        for link in links:
            try:
                candidate = extract_candidate(session, source, link, since)
            except requests.RequestException as exc:
                print(f"[warn] failed to read article {link}: {exc}", file=sys.stderr)
                continue
            if candidate:
                candidates.append(candidate)
    deduped: dict[str, Candidate] = {}
    for item in candidates:
        deduped[item.url] = item
    return sorted(
        deduped.values(),
        key=lambda item: (item.priority, item.publish_date or "", item.keyword_hits),
        reverse=False,
    )


def build_user_prompt(candidates: list[Candidate], today: str) -> str:
    payload = [asdict(item) for item in candidates]
    return f"""Today is {today}.
Analyze these candidate articles and return JSON with this schema:
{{
  "full_digest_worthy": true,
  "executive_summary_zh": ["sentence", "..."],
  "executive_summary_en": ["sentence", "..."],
  "items": [
    {{
      "title": "",
      "source": "",
      "author": "",
      "publish_date": "",
      "url": "",
      "summary_zh": "",
      "summary_en": "",
      "why_it_matters_zh": "",
      "why_it_matters_en": "",
      "key_takeaways_zh": ["", ""],
      "key_takeaways_en": ["", ""],
      "tags": ["", ""],
      "signal_score": 1,
      "novelty_score": 1,
      "actionability_score": 1
    }}
  ],
  "top_items": ["title 1", "title 2", "title 3"],
  "new_terms_zh": ["", ""],
  "new_terms_en": ["", ""],
  "themes_zh": ["", ""],
  "themes_en": ["", ""],
  "implications_zh": ["", ""],
  "implications_en": ["", ""],
  "reading_order": ["", ""],
  "what_to_ignore_zh": ["", ""],
  "what_to_ignore_en": ["", ""]
}}

Use Chinese and English content separately inside the JSON. Keep only high-signal items.
Candidates:
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""


def call_model(model: str, candidates: list[Candidate], today: str) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(candidates, today)},
        ],
    )
    text = response.output_text.strip()
    return json.loads(text)


def render_item_markdown(item: dict, lang: str) -> str:
    suffix = "zh" if lang == "zh" else "en"
    summary_key = f"summary_{suffix}"
    why_key = f"why_it_matters_{suffix}"
    takeaways_key = f"key_takeaways_{suffix}"
    lines = [
        f"## {item['title']}",
        f"- Source: {item['source']}",
        f"- Author: {item.get('author') or 'N/A'}",
        f"- Publish date: {item.get('publish_date') or 'N/A'}",
        f"- URL: {item['url']}",
        "",
        item[summary_key],
        "",
        f"Why it matters: {item[why_key]}",
        "",
        "Key takeaways:",
    ]
    for takeaway in item[takeaways_key]:
        lines.append(f"- {takeaway}")
    lines.extend(
        [
            "",
            f"Tags: {', '.join(item['tags'])}",
            f"Scores: signal {item['signal_score']}/5, novelty {item['novelty_score']}/5, actionability {item['actionability_score']}/5",
            "",
        ]
    )
    return "\n".join(lines)


def render_digest(result: dict, today: str, lang: str, candidates: list[Candidate]) -> str:
    suffix = "zh" if lang == "zh" else "en"
    title = "# AI Coding Daily Digest - " + today if lang == "en" else "# AI Coding Daily Digest - " + today
    summary_lines = result.get(f"executive_summary_{suffix}", [])
    if not result.get("full_digest_worthy", True) and not result.get("items"):
        warning = (
            "Today has no high-signal AI coding updates worth a full digest."
            if lang == "en"
            else "Today has no high-signal AI coding updates worth a full digest."
        )
        return f"{title}\n\n{warning}\n"

    lines = [title, "", "## Executive Summary", *[f"- {line}" for line in summary_lines], ""]
    lines.append("## Selected Items")
    lines.append("")
    for item in result["items"]:
        lines.append(render_item_markdown(item, lang))

    lines.extend(["## Top Items", ""])
    for entry in result.get("top_items", [])[:3]:
        lines.append(f"- {entry}")
    lines.extend(["", "## New Terms", ""])
    for entry in result.get(f"new_terms_{suffix}", []):
        lines.append(f"- {entry}")
    lines.extend(["", "## Themes", ""])
    for entry in result.get(f"themes_{suffix}", []):
        lines.append(f"- {entry}")
    lines.extend(["", "## Implications", ""])
    for entry in result.get(f"implications_{suffix}", []):
        lines.append(f"- {entry}")
    lines.extend(["", "## Recommended Reading Order", ""])
    for entry in result.get("reading_order", []):
        lines.append(f"- {entry}")
    if result.get(f"what_to_ignore_{suffix}"):
        lines.extend(["", "## What to Ignore", ""])
        for entry in result.get(f"what_to_ignore_{suffix}", []):
            lines.append(f"- {entry}")
    lines.extend(["", "## Sources Checked", ""])
    for item in candidates:
        lines.append(f"- [{item.source}]({item.landing_url})")
    return "\n".join(lines) + "\n"


def write_outputs(today: str, result: dict, candidates: list[Candidate]) -> None:
    zh_body = render_digest(result, today, "zh", candidates)
    en_body = render_digest(result, today, "en", candidates)

    files = {
        CONTENT_DIR / f"{today}.zh.md": zh_body,
        CONTENT_DIR / f"{today}.en.md": en_body,
        CONTENT_DIR / "latest.zh.md": zh_body,
        CONTENT_DIR / "latest.en.md": en_body,
        DATA_RAW_DIR / f"{today}.json": json.dumps([asdict(item) for item in candidates], ensure_ascii=False, indent=2),
        DATA_PROCESSED_DIR / f"{today}.json": json.dumps(result, ensure_ascii=False, indent=2),
    }
    for path, body in files.items():
        path.write_text(body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", default=slug_date(now_utc()))
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-5.4"))
    args = parser.parse_args()

    ensure_dirs()
    today_dt = datetime.strptime(args.today, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    candidates = collect_candidates(today_dt)
    if not candidates:
        raise RuntimeError("No candidates collected. Check source fetchers or network access.")
    result = call_model(args.model, candidates, args.today)
    write_outputs(args.today, result, candidates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
