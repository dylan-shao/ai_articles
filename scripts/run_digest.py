#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import warnings
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, FeatureNotFound, XMLParsedAsHTMLWarning
from openai import OpenAI, OpenAIError, RateLimitError


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "sources.json"
CONTENT_DIR = ROOT / "content"
DATA_RAW_DIR = ROOT / "data" / "raw"
DATA_PROCESSED_DIR = ROOT / "data" / "processed"
DATA_COLLECTIONS_DIR = ROOT / "data" / "collections"
HARNESS_LIBRARY_PATH = DATA_COLLECTIONS_DIR / "harness_articles.json"
DEFAULT_TIMEOUT = 20
MAX_LINKS_PER_SOURCE = 16
MIN_KEYWORD_HITS = 2
RECENT_DIGEST_DEDUPE_DAYS = 3
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
HARNESS_KEYWORDS = [
    "harness",
    "scaffold",
    "scaffolding",
    "long-running",
    "context engineering",
    "agent sdk",
    "agentic coding",
    "coding eval",
    "eval infrastructure",
    "mcp",
    "tool use",
    "multi-agent",
]

SYSTEM_PROMPT = """You are an AI coding daily intelligence analyst.
Return valid JSON only.
Select the highest-signal items from the candidate list for an experienced backend/platform/engineering lead.
Prioritize original technical sources about AI coding agents, coding evals, harness design, MCP, repo understanding, developer tooling, and organizational adoption of AI coding.
Exclude generic AI news, fundraising, partnerships, shallow launches, reposts, or opinion pieces without technical insight.
Prefer 2-8 items. If the day is weak, return only the strong items.
If no item is strong enough, set `full_digest_worthy` to false and keep at most 3 borderline items.
"""

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


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


def fallback_item(candidate: Candidate) -> dict:
    published = candidate.publish_date or "Unknown"
    summary_zh = (
        f"该候选来自 {candidate.source}，标题与摘要显示其与 AI coding / developer tooling 主题相关。"
        "由于本次云端运行未完成模型精排，这里保留为待人工确认的边缘项。"
    )
    summary_en = (
        f"This candidate comes from {candidate.source} and appears relevant to AI coding or developer tooling."
        " The cloud run did not complete model ranking, so it is being retained as a borderline item."
    )
    return {
        "title": candidate.title,
        "source": candidate.source,
        "author": candidate.author or "",
        "publish_date": published,
        "url": candidate.url,
        "summary_zh": summary_zh,
        "summary_en": summary_en,
        "why_it_matters_zh": "当模型调用失败时，它至少能保留今天抓到的高相关原始来源，避免整条流水线中断。",
        "why_it_matters_en": "When the model call fails, this preserves the strongest raw sources instead of breaking the whole pipeline.",
        "key_takeaways_zh": [
            f"来源优先级: Tier {candidate.priority}",
            f"关键词命中数: {candidate.keyword_hits}",
        ],
        "key_takeaways_en": [
            f"Source priority: Tier {candidate.priority}",
            f"Keyword hits: {candidate.keyword_hits}",
        ],
        "tags": ["fallback", "candidate-review"],
        "signal_score": min(max(candidate.keyword_hits, 1), 5),
        "novelty_score": 2,
        "actionability_score": 2,
    }


def build_fallback_result(candidates: list[Candidate], today: str, error_message: str) -> dict:
    shortlisted = sorted(
        candidates,
        key=lambda item: (item.priority, -(item.keyword_hits), item.publish_date or ""),
    )[:3]
    return {
        "full_digest_worthy": False,
        "generated_via_fallback": True,
        "generation_error": error_message,
        "executive_summary_zh": [
            f"{today} 的云端日报抓取成功，但模型总结阶段失败。",
            "本次产出使用降级模板，仅保留最相关的候选来源供人工快速浏览。",
            "最常见原因是 API quota 不足、账单问题，或临时模型调用错误。",
        ],
        "executive_summary_en": [
            f"The {today} cloud digest collected sources successfully but failed during model summarization.",
            "This output uses a fallback template and keeps only the most relevant candidates for quick review.",
            "The most common causes are insufficient API quota, billing issues, or transient model errors.",
        ],
        "items": [fallback_item(candidate) for candidate in shortlisted],
        "top_items": [candidate.title for candidate in shortlisted[:3]],
        "new_terms_zh": ["insufficient_quota", "fallback digest"],
        "new_terms_en": ["insufficient_quota", "fallback digest"],
        "themes_zh": ["云端调度正常，但模型额度不足会让总结阶段失败。", "需要把抓取与总结解耦，保证站点可持续更新。"],
        "themes_en": ["Cloud scheduling can succeed even when model quota fails.", "Source collection and summarization should be decoupled so the site keeps updating."],
        "implications_zh": ["为生产环境准备备用模型或降级路径。", "监控 API quota 和账单状态，避免整条流水线硬失败。"],
        "implications_en": ["Prepare a backup model or fallback path for production.", "Monitor API quota and billing so the whole pipeline does not hard-fail."],
        "reading_order": [candidate.url for candidate in shortlisted],
        "what_to_ignore_zh": [f"本次完整总结未生成，原因: {error_message}"],
        "what_to_ignore_en": [f"The full digest was not generated because: {error_message}"],
    }


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_sources() -> list[dict]:
    return json.loads(CONFIG_PATH.read_text())


def slug_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def ensure_dirs() -> None:
    for directory in [CONTENT_DIR, DATA_RAW_DIR, DATA_PROCESSED_DIR, DATA_COLLECTIONS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def load_recent_digest_urls(today: str, lookback_days: int = RECENT_DIGEST_DEDUPE_DAYS) -> set[str]:
    today_dt = datetime.strptime(today, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    seen_urls: set[str] = set()
    for offset in range(1, lookback_days + 1):
        day = slug_date(today_dt - timedelta(days=offset))
        path = DATA_PROCESSED_DIR / f"{day}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            print(f"[warn] failed to parse historical digest {path.name}: {exc}", file=sys.stderr)
            continue
        for item in payload.get("items", []):
            url = item.get("url")
            if url:
                seen_urls.add(url)
    return seen_urls


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
    if not any(parsed.path.startswith(prefix) for prefix in source["allowed_path_prefixes"]):
        return False
    excluded_prefixes = source.get("excluded_path_prefixes", [])
    return not any(parsed.path.startswith(prefix) for prefix in excluded_prefixes)


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
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    response.raise_for_status()
    return response


def make_soup(body: str, url: str, content_type: str | None = None) -> BeautifulSoup:
    lower_type = (content_type or "").lower()
    lower_url = url.lower()
    parse_as_xml = (
        "xml" in lower_type
        or lower_url.endswith(".xml")
        or lower_url.endswith(".rss")
        or lower_url.endswith("/feed")
    )
    if parse_as_xml:
        try:
            return BeautifulSoup(body, "xml")
        except FeatureNotFound:
            pass
    return BeautifulSoup(body, "html.parser")


def extract_links(session: requests.Session, source: dict) -> list[str]:
    response = fetch(session, source["landing_url"])
    html = response.text
    soup = make_soup(html, source["landing_url"], response.headers.get("Content-Type"))
    seen = set()
    links: list[str] = []
    loc_tags = soup.find_all("loc")
    if loc_tags:
        for tag in loc_tags:
            href = clean_text(tag.get_text(" ", strip=True))
            href = href.split("#", 1)[0]
            if not href or href in seen or not allowed_link(href, source):
                continue
            seen.add(href)
            links.append(href)
            if len(links) >= MAX_LINKS_PER_SOURCE:
                break
        return links
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
    response = fetch(session, article_url)
    html = response.text
    soup = make_soup(html, article_url, response.headers.get("Content-Type"))
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


def collect_candidates(now: datetime, today: str) -> list[Candidate]:
    since = now - timedelta(hours=30)
    recent_digest_urls = load_recent_digest_urls(today)
    session = requests.Session()
    candidates: list[Candidate] = []
    for source in load_sources():
        source_hits = 0
        skipped_for_history = 0
        try:
            links = extract_links(session, source)
        except requests.RequestException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            is_optional = source.get("optional", False)
            if is_optional and status_code in {401, 403, 429}:
                print(
                    f"[info] skipped optional source {source['name']} due to HTTP {status_code}",
                    file=sys.stderr,
                )
            else:
                print(f"[warn] failed to read {source['name']}: {exc}", file=sys.stderr)
            continue
        for link in links:
            try:
                candidate = extract_candidate(session, source, link, since)
            except requests.RequestException as exc:
                print(f"[warn] failed to read article {link}: {exc}", file=sys.stderr)
                continue
            except Exception as exc:
                print(f"[warn] failed to parse article {link}: {exc}", file=sys.stderr)
                continue
            if candidate:
                if candidate.url in recent_digest_urls:
                    skipped_for_history += 1
                    continue
                candidates.append(candidate)
                source_hits += 1
        print(
            f"[info] {source['name']}: kept {source_hits} candidates from {len(links)} links"
            f" ({skipped_for_history} skipped as recent digest repeats)"
        )
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
        return build_fallback_result(candidates, today, "OPENAI_API_KEY is missing")

    client = OpenAI(api_key=api_key)
    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(candidates, today)},
            ],
        )
        text = response.output_text.strip()
        return json.loads(text)
    except RateLimitError as exc:
        return build_fallback_result(candidates, today, f"OpenAI quota error: {exc}")
    except (OpenAIError, json.JSONDecodeError) as exc:
        return build_fallback_result(candidates, today, f"Model generation error: {exc}")


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


def is_harness_related(item: dict) -> bool:
    text = " ".join(
        [
            item.get("title", ""),
            item.get("summary_zh", ""),
            item.get("summary_en", ""),
            item.get("why_it_matters_zh", ""),
            item.get("why_it_matters_en", ""),
            " ".join(item.get("tags", [])),
        ]
    ).lower()
    return any(keyword in text for keyword in HARNESS_KEYWORDS)


def update_harness_library(today: str, result: dict) -> None:
    if HARNESS_LIBRARY_PATH.exists():
        payload = json.loads(HARNESS_LIBRARY_PATH.read_text())
    else:
        payload = {"updated_at": today, "items": []}

    items = payload.get("items", [])
    known_urls = {entry["url"] for entry in items}
    additions = 0
    for item in result.get("items", []):
        if not is_harness_related(item):
            continue
        if item["url"] in known_urls:
            continue
        items.append(
            {
                "title": item["title"],
                "url": item["url"],
                "summary": item.get("summary_zh") or item.get("summary_en") or "",
                "published_date": item.get("publish_date") or today,
                "source": item.get("source") or "",
                "added_from": "daily_digest",
                "added_on": today,
            }
        )
        known_urls.add(item["url"])
        additions += 1

    payload["updated_at"] = today
    payload["items"] = sorted(items, key=lambda entry: entry.get("published_date", ""), reverse=True)
    HARNESS_LIBRARY_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[info] harness library updated with {additions} new items")


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
    update_harness_library(today, result)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", default=slug_date(now_utc()))
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-5.4"))
    args = parser.parse_args()

    ensure_dirs()
    today_dt = datetime.strptime(args.today, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    candidates = collect_candidates(today_dt, args.today)
    print(f"[info] collected {len(candidates)} total candidates")
    if not candidates:
        raise RuntimeError("No candidates collected. Check source fetchers or network access.")
    print(f"[info] generating digest with model {args.model}")
    result = call_model(args.model, candidates, args.today)
    if result.get("generated_via_fallback"):
        print(f"[warn] generated fallback digest: {result.get('generation_error', 'unknown error')}", file=sys.stderr)
    write_outputs(args.today, result, candidates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
