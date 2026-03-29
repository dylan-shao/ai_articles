#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
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
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, FeatureNotFound, XMLParsedAsHTMLWarning
from openai import OpenAI, OpenAIError, RateLimitError


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "sources.json"
CONTENT_DIR = ROOT / "content"
DATA_RAW_DIR = ROOT / "data" / "raw"
DATA_PROCESSED_DIR = ROOT / "data" / "processed"
DATA_COLLECTIONS_DIR = ROOT / "data" / "collections"
MANUAL_VIDEO_OVERRIDES_PATH = ROOT / "data" / "manual_video_overrides.json"
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

VIDEO_SUMMARY_SYSTEM_PROMPT = """You summarize long-form technical YouTube videos for an engineering audience.
Return valid JSON only.
Use the transcript as the source of truth and do not invent details that are not supported by it.
Keep the output concise, concrete, and useful for a reader who wants the key arguments and exact moments worth replaying.
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
    youtube_url: str | None = None
    youtube_video_id: str | None = None


@dataclass
class TranscriptSegment:
    start_seconds: int
    duration_seconds: int
    text: str


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


def build_empty_day_result(today: str, reason: str) -> dict:
    return {
        "full_digest_worthy": False,
        "generated_via_empty_day": True,
        "generation_reason": reason,
        "executive_summary_zh": [
            f"{today} 没有新增的高信号候选进入日报。",
            "这通常意味着来源站点当天没有足够相关的新文章，或者候选都被最近几天的跨天去重规则过滤掉了。",
            "流水线本次会继续产出站点文件，但保留为空日报而不是直接失败。",
        ],
        "executive_summary_en": [
            f"No new high-signal candidates made it into the digest for {today}.",
            "This usually means the source set did not publish sufficiently relevant new articles, or every candidate was filtered by recent cross-day dedupe.",
            "The pipeline will still publish site artifacts for the day instead of failing the run.",
        ],
        "items": [],
        "top_items": [],
        "new_terms_zh": ["空日报", "跨天去重"],
        "new_terms_en": ["empty digest", "cross-day dedupe"],
        "themes_zh": ["低信号日期应该稳定产出，而不是让自动化流程报错。", "跨天去重需要和空日报策略一起工作，避免重复内容与任务失败同时出现。"],
        "themes_en": ["Low-signal days should still produce a stable artifact instead of failing automation.", "Cross-day dedupe should work together with an empty-digest path so duplicate suppression does not break the job."],
        "implications_zh": ["站点与归档会继续按日更新，即使当天没有新内容。", "后续如需更激进的策略，可以把被去重文章单独标记为“昨日已覆盖”。"],
        "implications_en": ["The site and archive can keep updating daily even when there is no new content.", "If needed, we can later add an explicit 'already covered recently' note for deduped articles."],
        "reading_order": [],
        "what_to_ignore_zh": [reason],
        "what_to_ignore_en": [reason],
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


def parse_canonical_url(soup: BeautifulSoup, fallback_url: str) -> str:
    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical and canonical.get("href"):
        return canonical["href"].strip()
    og_url = soup.find("meta", attrs={"property": "og:url"})
    if og_url and og_url.get("content"):
        return og_url["content"].strip()
    return fallback_url


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


def extract_youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
        return video_id or None
    if host in {"youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/embed/") or parsed.path.startswith("/shorts/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 2:
                return parts[1]
    return None


def canonical_youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def extract_youtube_url(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    candidates: list[tuple[str, str]] = []
    for tag in soup.find_all(["a", "iframe"], href=True):
        href = tag.get("href")
        if not href:
            continue
        video_id = extract_youtube_video_id(href)
        if video_id:
            candidates.append((canonical_youtube_url(video_id), video_id))
    for tag in soup.find_all("iframe", src=True):
        src = tag.get("src")
        if not src:
            continue
        video_id = extract_youtube_video_id(src)
        if video_id:
            candidates.append((canonical_youtube_url(video_id), video_id))
    if not candidates:
        return (None, None)
    seen_video_ids: set[str] = set()
    for url, video_id in candidates:
        if video_id in seen_video_ids:
            continue
        seen_video_ids.add(video_id)
        return (url, video_id)
    return (None, None)


def format_seconds(seconds: int) -> str:
    hours, remainder = divmod(max(seconds, 0), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def extract_caption_tracks(player_response: dict) -> list[dict]:
    captions = player_response.get("captions", {})
    renderer = captions.get("playerCaptionsTracklistRenderer", {})
    return renderer.get("captionTracks", []) or []


def choose_caption_track(tracks: list[dict]) -> dict | None:
    if not tracks:
        return None
    preferred_scores: list[tuple[int, dict]] = []
    for track in tracks:
        score = 0
        language_code = (track.get("languageCode") or "").lower()
        kind = (track.get("kind") or "").lower()
        name = clean_text(track.get("name", {}).get("simpleText", ""))
        if language_code.startswith("en"):
            score += 10
        if kind != "asr":
            score += 4
        if "english" in name.lower():
            score += 2
        preferred_scores.append((score, track))
    preferred_scores.sort(key=lambda entry: entry[0], reverse=True)
    return preferred_scores[0][1]


def fetch_youtube_transcript(session: requests.Session, video_id: str) -> list[TranscriptSegment]:
    watch_url = canonical_youtube_url(video_id)
    response = fetch(session, watch_url)
    html_body = response.text
    player_match = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.+?\})\s*;", html_body, re.DOTALL)
    if not player_match:
        return []
    player_response = json.loads(player_match.group(1))
    track = choose_caption_track(extract_caption_tracks(player_response))
    if not track or not track.get("baseUrl"):
        return []
    transcript_response = fetch(session, f"{track['baseUrl']}&fmt=json3")
    transcript_payload = transcript_response.json()
    segments: list[TranscriptSegment] = []
    for event in transcript_payload.get("events", []):
        if "segs" not in event:
            continue
        text = clean_text("".join(seg.get("utf8", "") for seg in event.get("segs", [])))
        text = html.unescape(text)
        if not text:
            continue
        start_seconds = int(event.get("tStartMs", 0) / 1000)
        duration_seconds = max(int(event.get("dDurationMs", 0) / 1000), 0)
        segments.append(
            TranscriptSegment(
                start_seconds=start_seconds,
                duration_seconds=duration_seconds,
                text=text,
            )
        )
    return segments


def build_video_summary_prompt(item: dict, transcript: str) -> str:
    return f"""Article: {item.get('title', '')}
Article URL: {item.get('url', '')}

Summarize this technical video transcript for an engineering reader.
Return JSON with this shape:
{{
  "overview_zh": "...",
  "overview_en": "...",
  "highlights": [
    {{
      "start_seconds": 123,
      "title_zh": "...",
      "title_en": "...",
      "summary_zh": "...",
      "summary_en": "..."
    }}
  ]
}}

Rules:
- Keep 4 to 8 highlight segments.
- Each highlight must point to a real moment from the transcript.
- `start_seconds` must match the start of the discussed moment.
- Focus on the most actionable technical ideas, claims, methods, warnings, or examples.
- Keep each summary to 1 or 2 sentences.

Transcript:
{transcript}
"""


def summarize_video_with_model(client: OpenAI, model: str, item: dict, segments: list[TranscriptSegment]) -> dict | None:
    if not segments:
        return None
    transcript = "\n".join(f"[{format_seconds(segment.start_seconds)}] {segment.text}" for segment in segments)
    if len(transcript) > 120000:
        transcript = transcript[:120000]
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": VIDEO_SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": build_video_summary_prompt(item, transcript)},
        ],
    )
    payload = json.loads(response.output_text.strip())
    highlights = []
    for highlight in payload.get("highlights", []):
        start_seconds = int(highlight.get("start_seconds", 0))
        highlights.append(
            {
                "start_seconds": start_seconds,
                "timecode": format_seconds(start_seconds),
                "title_zh": clean_text(highlight.get("title_zh", "")),
                "title_en": clean_text(highlight.get("title_en", "")),
                "summary_zh": clean_text(highlight.get("summary_zh", "")),
                "summary_en": clean_text(highlight.get("summary_en", "")),
            }
        )
    if not highlights:
        return None
    return {
        "overview_zh": clean_text(payload.get("overview_zh", "")),
        "overview_en": clean_text(payload.get("overview_en", "")),
        "summary_basis_zh": "根据完整视频 transcript 生成的重点总结与时间片段。",
        "summary_basis_en": "Structured highlights generated from the full video transcript.",
        "highlights": highlights,
    }


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "video"


def build_video_slug(item: dict, video_id: str) -> str:
    return f"{slugify(item.get('title', 'video'))}-{video_id}"


def load_manual_video_overrides() -> dict:
    if not MANUAL_VIDEO_OVERRIDES_PATH.exists():
        return {}
    try:
        return json.loads(MANUAL_VIDEO_OVERRIDES_PATH.read_text())
    except json.JSONDecodeError as exc:
        print(f"[warn] failed to parse manual video overrides: {exc}", file=sys.stderr)
        return {}


def build_manual_video_payload(item: dict, override: dict) -> dict:
    video_id = override["video_id"]
    payload = {
        "video_id": video_id,
        "youtube_url": override.get("youtube_url") or canonical_youtube_url(video_id),
        "embed_url": f"https://www.youtube.com/embed/{video_id}?rel=0",
        "slug": build_video_slug(item, video_id),
        "overview_zh": clean_text(override.get("overview_zh", "")),
        "overview_en": clean_text(override.get("overview_en", "")),
        "summary_basis_zh": clean_text(override.get("summary_basis_zh", "")),
        "summary_basis_en": clean_text(override.get("summary_basis_en", "")),
        "highlights": [],
    }
    for highlight in override.get("highlights", []):
        start_seconds = int(highlight.get("start_seconds", 0))
        payload["highlights"].append(
            {
                "start_seconds": start_seconds,
                "timecode": highlight.get("timecode") or format_seconds(start_seconds),
                "title_zh": clean_text(highlight.get("title_zh", "")),
                "title_en": clean_text(highlight.get("title_en", "")),
                "summary_zh": clean_text(highlight.get("summary_zh", "")),
                "summary_en": clean_text(highlight.get("summary_en", "")),
            }
        )
    return payload


def enrich_result_with_video_data(result: dict, candidates: list[Candidate], model: str, today: str) -> dict:
    items = result.get("items", [])
    if not items:
        return result
    manual_overrides = load_manual_video_overrides()
    api_key = os.environ.get("OPENAI_API_KEY")
    candidate_map = {candidate.url: candidate for candidate in candidates}
    session = requests.Session()
    client = OpenAI(api_key=api_key) if api_key else None
    video_cache: dict[str, dict | None] = {}
    for item in items:
        override = manual_overrides.get(today, {}).get(item.get("url", ""))
        if override:
            item["video"] = build_manual_video_payload(item, override)
            continue
        candidate = candidate_map.get(item.get("url", ""))
        if not candidate or not candidate.youtube_video_id:
            continue
        if not client:
            continue
        video_id = candidate.youtube_video_id
        if video_id not in video_cache:
            try:
                segments = fetch_youtube_transcript(session, video_id)
                summary = summarize_video_with_model(client, model, item, segments)
                if summary:
                    video_cache[video_id] = {
                        "video_id": video_id,
                        "youtube_url": candidate.youtube_url or canonical_youtube_url(video_id),
                        "embed_url": f"https://www.youtube.com/embed/{video_id}?rel=0",
                        "slug": build_video_slug(item, video_id),
                        **summary,
                    }
                else:
                    video_cache[video_id] = None
            except (requests.RequestException, OpenAIError, json.JSONDecodeError, ValueError) as exc:
                print(f"[warn] failed to enrich video for {item.get('url', '')}: {exc}", file=sys.stderr)
                video_cache[video_id] = None
        if video_cache[video_id]:
            item["video"] = video_cache[video_id]
    return result


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
    normalized_url = parse_canonical_url(soup, article_url)

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
    youtube_url, youtube_video_id = extract_youtube_url(soup)

    return Candidate(
        title=title,
        source=source["name"],
        url=normalized_url,
        landing_url=source["landing_url"],
        priority=source["priority"],
        publish_date=publish_dt.isoformat() if publish_dt else None,
        author=author,
        excerpt=excerpt,
        body_excerpt=body_excerpt,
        keyword_hits=keyword_hits,
        youtube_url=youtube_url,
        youtube_video_id=youtube_video_id,
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
    video = item.get("video")
    video_icon = ""
    if video and video.get("slug"):
        video_page = f"video-{video['slug']}.{lang}.html"
        video_label = "查看视频总结" if lang == "zh" else "Open video summary"
        video_icon = (
            f" <a class=\"video-icon-link\" href=\"{video_page}\" title=\"{video_label}\" "
            f"aria-label=\"{video_label}\">"
            "<span aria-hidden=\"true\">▶</span>"
            "</a>"
        )
    lines = [
        f"## {item['title']}{video_icon}",
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
                "video": item.get("video"),
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
        reason = "No new candidates survived collection after source filtering and recent-digest dedupe."
        print(f"[warn] {reason}", file=sys.stderr)
        write_outputs(args.today, build_empty_day_result(args.today, reason), candidates)
        return 0
    print(f"[info] generating digest with model {args.model}")
    result = call_model(args.model, candidates, args.today)
    if result.get("generated_via_fallback"):
        print(f"[warn] generated fallback digest: {result.get('generation_error', 'unknown error')}", file=sys.stderr)
    result = enrich_result_with_video_data(result, candidates, args.model, args.today)
    write_outputs(args.today, result, candidates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
