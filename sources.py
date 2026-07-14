"""
Source fetchers — one function per job board, all returning list[dict]
conforming to the SCHEMA defined in fetch.py.
"""

from common import make_posting, log, UA

import httpx


def fetch_remoteok(client: httpx.Client) -> list[dict]:
    """RemoteOK official public JSON API. Query ?tag=python and ?tag=backend
    separately, merge by job id to avoid duplicates."""
    seen_ids: set[str] = set()
    out = []

    for tag in ("python", "backend"):
        try:
            r = client.get(f"https://remoteok.com/api?tag={tag}", headers=UA)
            r.raise_for_status()
            items = [x for x in r.json() if isinstance(x, dict) and x.get("id")]
        except Exception as e:
            log(f"[remoteok/{tag}] request failed: {e}")
            continue

        for x in items:
            jid = str(x["id"])
            if jid in seen_ids:
                continue
            seen_ids.add(jid)

            salary = ""
            lo, hi = x.get("salary_min"), x.get("salary_max")
            if lo or hi:
                salary = f"${lo or '?'}–${hi or '?'}"
            posted = (x.get("date") or "")[:10]
            tags_list = x.get("tags") or []
            out.append(
                make_posting(
                    title=x.get("position"),
                    company=x.get("company"),
                    url=x.get("url"),
                    source="remoteok",
                    salary=salary,
                    location=x.get("location") or "Remote",
                    posted_at=posted,
                    description=(x.get("description") or "")[:2000],
                    tags=", ".join(tags_list) if isinstance(tags_list, list) else str(tags_list),
                )
            )
    return out


def fetch_remotive(client: httpx.Client) -> list[dict]:
    """Remotive public JSON API — software-dev category, no key needed."""
    r = client.get(
        "https://remotive.com/api/remote-jobs",
        params={"category": "software-dev", "limit": 200},
        headers=UA,
    )
    r.raise_for_status()
    jobs = r.json().get("jobs", [])
    out = []
    for x in jobs:
        tags_list = x.get("tags") or []
        out.append(
            make_posting(
                title=x.get("title"),
                company=x.get("company_name"),
                url=x.get("url"),
                source="remotive",
                salary=x.get("salary") or "",
                location=x.get("candidate_required_location") or "Remote",
                posted_at=(x.get("publication_date") or "")[:10],
                description=(x.get("description") or "")[:2000],
                tags=", ".join(tags_list) if isinstance(tags_list, list) else str(tags_list),
            )
        )
    return out


def fetch_wwr_rss(client: httpx.Client) -> list[dict]:
    """We Work Remotely — back-end programming RSS feed, parsed with feedparser."""
    import feedparser

    r = client.get(
        "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
        headers=UA,
    )
    r.raise_for_status()
    feed = feedparser.parse(r.text)
    out = []
    for entry in feed.entries:
        title_raw = entry.get("title", "")
        company, _, title = title_raw.partition(": ")
        if not title:
            title, company = company, ""

        posted = ""
        if entry.get("published_parsed"):
            from time import strftime
            posted = strftime("%Y-%m-%d", entry.published_parsed)

        region = entry.get("region", "")
        out.append(
            make_posting(
                title=title.strip(),
                company=company.strip(),
                url=entry.get("link", ""),
                source="wwr",
                salary="",
                location=region or "Remote",
                posted_at=posted,
                description=(entry.get("summary") or "")[:2000],
                tags=entry.get("category", ""),
            )
        )
    return out


def fetch_jobicy(client: httpx.Client) -> list[dict]:
    """Jobicy public API — supports server-side tag filtering."""
    out = []
    for tag in ("python", "backend"):
        try:
            r = client.get(
                "https://jobicy.com/api/v2/remote-jobs",
                params={"count": 50, "tag": tag},
                headers=UA,
            )
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
        except Exception as e:
            log(f"[jobicy/{tag}] request failed: {e}")
            continue

        for x in jobs:
            out.append(
                make_posting(
                    title=x.get("jobTitle", ""),
                    company=x.get("companyName", ""),
                    url=x.get("url", ""),
                    source="jobicy",
                    salary="",
                    location=x.get("jobGeo", "") or "Remote",
                    posted_at=(x.get("pubDate") or "")[:10],
                    description=(x.get("jobDescription") or "")[:2000],
                    tags=", ".join(x.get("jobIndustry", [])) if isinstance(x.get("jobIndustry"), list) else "",
                )
            )
    return out
