from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from app.db import get_db
from app.gog import gog_cli
from app.tools.markupgo_client import MarkupGoClient
from app.tools.browseract import scrape_url


_PUBLISHERS: dict[str, tuple[str, ...]] = {
    "The Economist": ("economist.com",),
    "The Atlantic": ("theatlantic.com", "atlantic.com"),
    "The New York Times": ("nytimes.com",),
}

_INTERESTING_RE = re.compile(
    r"(?i)\b(ai|artificial intelligence|policy|economy|market|geopolit|war|energy|europe|china|usa|tech|automation|productivity|science|strategy|risk)\b"
)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9\\-]{3,}")
_STOP = {
    "with", "from", "that", "this", "have", "your", "their", "will", "about", "into", "over", "after",
    "would", "could", "should", "today", "tomorrow", "meeting", "review", "update", "thread", "email",
    "calendar", "event", "task", "notes", "briefing", "assistant", "executive",
}


@dataclass
class Article:
    publisher: str
    domain: str
    title: str
    url: str
    summary: str
    content: str
    image_url: str
    published_at: str
    score: float


def _publisher_for_domain(domain: str) -> str | None:
    d = (domain or "").lower().strip()
    for name, needles in _PUBLISHERS.items():
        if any(n in d for n in needles):
            return name
    return None


def _as_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return str(v).strip()


def _extract_json_list(text: str) -> list[Any]:
    try:
        clean = (text or "").strip()
        m = re.search(r"\[[\s\S]*\]", clean)
        if not m:
            return []
        arr = json.loads(m.group(0))
        return arr if isinstance(arr, list) else []
    except Exception:
        return []


def _tokenize(text: str) -> list[str]:
    vals: list[str] = []
    for m in _WORD_RE.finditer((text or "").lower()):
        w = m.group(0)
        if w in _STOP:
            continue
        vals.append(w)
    return vals


def _walk(node: Any):
    if isinstance(node, dict):
        yield node
        for val in node.values():
            yield from _walk(val)
    elif isinstance(node, list):
        for val in node:
            yield from _walk(val)


def _extract_articles_from_payload(payload: dict[str, Any], default_ts: str) -> list[Article]:
    out: list[Article] = []
    seen: set[str] = set()
    for obj in _walk(payload):
        if not isinstance(obj, dict):
            continue
        url = _as_text(obj.get("url") or obj.get("link") or obj.get("article_url"))
        if not url.startswith("http"):
            continue
        domain = (urlparse(url).netloc or "").lower()
        publisher = _publisher_for_domain(domain) or _as_text(obj.get("publisher") or obj.get("source") or obj.get("site"))
        publisher = _publisher_for_domain(publisher) or _publisher_for_domain(domain)
        if not publisher:
            continue
        title = _as_text(
            obj.get("title")
            or obj.get("headline")
            or obj.get("name")
            or obj.get("article_title")
        )
        if not title:
            continue
        summary = _as_text(
            obj.get("summary")
            or obj.get("excerpt")
            or obj.get("description")
            or obj.get("content")
        )
        content = _as_text(
            obj.get("full_text")
            or obj.get("article_text")
            or obj.get("body")
            or obj.get("text")
            or obj.get("content")
        )
        image_url = _as_text(
            obj.get("image_url")
            or obj.get("hero_image")
            or obj.get("thumbnail")
            or obj.get("screenshot_url")
            or obj.get("cover")
        )
        published_at = _as_text(
            obj.get("published_at")
            or obj.get("published")
            or obj.get("date")
            or obj.get("timestamp")
            or default_ts
        )
        key = f"{url}|{title.lower()[:120]}"
        if key in seen:
            continue
        seen.add(key)
        score = 1.0
        if _INTERESTING_RE.search(f"{title} {summary}"):
            score += 1.0
        score += min(1.0, len(summary) / 500.0)
        out.append(
            Article(
                publisher=publisher,
                domain=domain,
                title=title,
                url=url,
                summary=summary,
                content=content,
                image_url=image_url,
                published_at=published_at,
                score=score,
            )
        )
    return out


def fetch_browseract_articles(
    *,
    tenant_candidates: list[str],
    lookback_days: int = 7,
    max_events: int = 120,
) -> list[Article]:
    since = datetime.now(timezone.utc) - timedelta(days=max(1, int(lookback_days)))
    db = get_db()
    rows = db.fetchall(
        """
        SELECT tenant, event_type, payload_json, created_at
        FROM external_events
        WHERE source='browseract'
          AND created_at >= %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (since, max_events),
    )
    if not rows:
        return []
    allowed = {x.strip() for x in tenant_candidates if x and x.strip()}
    articles: list[Article] = []
    for row in rows:
        tenant = _as_text(row.get("tenant"))
        if allowed and tenant not in allowed:
            continue
        payload = row.get("payload_json") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        if not isinstance(payload, dict):
            continue
        created = _as_text(row.get("created_at"))
        articles.extend(_extract_articles_from_payload(payload, created))
    dedup: dict[str, Article] = {}
    for a in sorted(articles, key=lambda x: x.score, reverse=True):
        if a.url not in dedup:
            dedup[a.url] = a
    return list(dedup.values())


def select_interesting(articles: list[Article], *, max_items: int = 12, signal_terms: set[str] | None = None) -> list[Article]:
    if not articles:
        return []
    sig = {s.lower().strip() for s in (signal_terms or set()) if s}
    rescored: list[Article] = []
    for a in articles:
        sc = a.score
        if sig:
            blob = f"{a.title} {a.summary}".lower()
            hits = 0
            for t in sig:
                if len(t) < 4:
                    continue
                if t in blob:
                    hits += 1
            if hits:
                sc += min(1.5, 0.35 * hits)
        rescored.append(
            Article(
                publisher=a.publisher,
                domain=a.domain,
                title=a.title,
                url=a.url,
                summary=a.summary,
                content=a.content,
                image_url=a.image_url,
                published_at=a.published_at,
                score=sc,
            )
        )
    buckets: dict[str, list[Article]] = {}
    for a in rescored:
        buckets.setdefault(a.publisher, []).append(a)
    for arr in buckets.values():
        arr.sort(key=lambda x: x.score, reverse=True)
    selected: list[Article] = []
    for pub in ("The Economist", "The Atlantic", "The New York Times"):
        if pub in buckets and buckets[pub]:
            selected.append(buckets[pub].pop(0))
    rest: list[Article] = []
    for arr in buckets.values():
        rest.extend(arr)
    rest.sort(key=lambda x: x.score, reverse=True)
    selected.extend(rest[: max(0, max_items - len(selected))])
    return selected[:max_items]


def _pdf_html(articles: list[Article], title: str) -> str:
    cards = []
    for idx, a in enumerate(articles, start=1):
        summary = a.summary[:600] + ("..." if len(a.summary) > 600 else "")
        full = (a.content or "").strip()
        if len(full) > 7000:
            full = full[:7000] + "..."
        image_block = ""
        if a.image_url.startswith("http"):
            image_block = f'<img src="{a.image_url}" alt="article image" />'
        cards.append(
            f"""
            <section class="card">
              <div class="accent"></div>
              <div class="meta">{idx}. {a.publisher} | {a.domain}</div>
              <h2>{a.title}</h2>
              {image_block}
              <p>{summary or "No summary provided by BrowserAct."}</p>
              <p class="full">{full or "Full text unavailable from payload. The link below is included for complete reading."}</p>
              <p><a href="{a.url}">{a.url}</a></p>
            </section>
            """
        )
    cards_html = "\n".join(cards)
    return f"""
    <html>
      <body>
        <div class="wrap">
          <header>
            <h1>{title}</h1>
            <div class="sub">Curated from BrowserAct | Economist / Atlantic / NYT</div>
          </header>
          {cards_html}
        </div>
      </body>
      <style>
        body {{
          font-family: Georgia, "Times New Roman", serif;
          background:
            radial-gradient(1200px 420px at 15% -20%, #d7ecff 0%, transparent 55%),
            radial-gradient(1100px 450px at 90% -10%, #ffe9cc 0%, transparent 50%),
            linear-gradient(180deg, #f7f9fc 0%, #ffffff 32%);
          color: #11161d;
          margin: 0;
          padding: 30px;
        }}
        .wrap {{ max-width: 1050px; margin: 0 auto; }}
        header {{
          padding: 22px 24px;
          border: 1px solid #d4dde9;
          border-radius: 14px;
          background: rgba(248, 251, 255, 0.85);
          margin-bottom: 18px;
        }}
        h1 {{ margin: 0; font-size: 36px; letter-spacing: 0.01em; }}
        .sub {{ margin-top: 6px; color: #3f4c5a; font-size: 14px; font-family: Arial, sans-serif; }}
        .card {{
          border: 1px solid #dce3ec;
          border-radius: 14px;
          padding: 18px 20px;
          margin: 12px 0;
          background: white;
          position: relative;
          box-shadow: 0 8px 24px rgba(17, 22, 29, 0.04);
        }}
        .accent {{
          position: absolute;
          left: 0;
          top: 0;
          width: 8px;
          height: 100%;
          border-radius: 14px 0 0 14px;
          background: linear-gradient(180deg, #0f62ad, #1fa3a0);
        }}
        .meta {{ color: #3f5871; font-size: 12px; letter-spacing: 0.02em; font-family: Arial, sans-serif; margin-left: 10px; }}
        h2 {{ margin: 8px 0 10px 10px; font-size: 24px; line-height: 1.24; }}
        p {{ margin: 8px 0 8px 10px; line-height: 1.5; font-size: 14px; font-family: Arial, sans-serif; color: #1d2733; }}
        p.full {{ font-size: 13px; color: #2d3947; white-space: pre-wrap; }}
        img {{
          margin: 10px 0 10px 10px;
          width: 95%;
          max-height: 380px;
          object-fit: cover;
          border-radius: 10px;
          border: 1px solid #d8e0ea;
          display: block;
        }}
        a {{ color: #0b5ea8; text-decoration: none; word-break: break-all; }}
      </style>
    </html>
    """


async def render_articles_pdf(articles: list[Article], *, title: str) -> bytes:
    html_doc = _pdf_html(articles, title)
    mg = MarkupGoClient()
    payload = {
        "source": {"type": "html", "data": html_doc},
        "options": {},
    }
    return await asyncio.wait_for(mg.render_pdf_buffer(payload, timeout_s=45.0), timeout=60.0)


async def collect_user_signal_terms(*, openclaw_container: str, google_account: str) -> set[str]:
    if not openclaw_container:
        return set()
    texts: list[str] = []

    async def _run(cmd: list[str], timeout: float = 8.0) -> None:
        try:
            out = await asyncio.wait_for(gog_cli(openclaw_container, cmd, google_account or ""), timeout=timeout)
            rows = _extract_json_list(out)
            for row in rows[:20]:
                if not isinstance(row, dict):
                    continue
                texts.append(
                    " ".join(
                        [
                            _as_text(row.get("summary")),
                            _as_text(row.get("title")),
                            _as_text(row.get("subject")),
                            _as_text(row.get("snippet")),
                        ]
                    )
                )
        except Exception:
            return

    await _run(["calendar", "events", "--max", "25", "--json"], timeout=9.0)
    await _run(["gmail", "messages", "search", "newer_than:3d", "--max", "30", "--json"], timeout=10.0)
    # Tasks require a tasklist id in gog >=0.11.0.
    try:
        tl_out = await asyncio.wait_for(
            gog_cli(openclaw_container, ["tasks", "lists", "list", "--max", "10", "--json"], google_account or ""),
            timeout=8.0,
        )
        for row in _extract_json_list(tl_out)[:3]:
            if not isinstance(row, dict):
                continue
            lid = _as_text(row.get("id"))
            if not lid:
                continue
            await _run(["tasks", "list", lid, "--max", "25", "--json"], timeout=9.0)
    except Exception:
        pass

    words: dict[str, int] = {}
    for txt in texts:
        for w in _tokenize(txt):
            words[w] = words.get(w, 0) + 1
    top = sorted(words.items(), key=lambda kv: kv[1], reverse=True)[:30]
    return {k for k, _ in top}


async def enrich_full_articles(articles: list[Article], *, max_fetch: int = 6) -> list[Article]:
    """
    Fill missing full text via BrowserAct scrape to make the PDF genuinely content-rich.
    """
    out: list[Article] = []
    fetch_budget = max(0, int(max_fetch))
    for a in articles:
        full = (a.content or "").strip()
        if len(full) < 700 and fetch_budget > 0 and a.url.startswith("http"):
            try:
                scraped = await asyncio.wait_for(scrape_url(a.url), timeout=35.0)
                if isinstance(scraped, str) and not scraped.lower().startswith("error:") and "failed to scrape" not in scraped.lower():
                    full = scraped.strip()
            except Exception:
                pass
            fetch_budget -= 1
        out.append(
            Article(
                publisher=a.publisher,
                domain=a.domain,
                title=a.title,
                url=a.url,
                summary=a.summary,
                content=full or a.content,
                image_url=a.image_url,
                published_at=a.published_at,
                score=a.score,
            )
        )
    return out
