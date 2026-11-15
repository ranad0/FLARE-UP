"""Inspect the live PSI investigation UI without downloading files.

This is a discovery step for the dynamic PSI file browser. It records visible
metadata, interactive labels, and redacted network request URLs so the downloader
can be built against observed site behavior instead of guessed endpoints.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import REPORTS_DIR

PSI_ID_RE = re.compile(r"^PSI-\d+$", re.IGNORECASE)
SENSITIVE_QUERY_KEYS = {
    "token", "access_token", "authorization", "signature", "sig",
    "api_key", "apikey", "key", "session", "sessionid", "csrf",
    "expires", "awsaccesskeyid", "x-amz-credential", "x-amz-signature",
    "x-amz-security-token", "x-amz-algorithm", "x-amz-date",
    "x-amz-expires", "x-amz-signedheaders",
}


def safe_url(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (key, "[redacted]" if key.lower() in SENSITIVE_QUERY_KEYS else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    if isinstance(value, str) and value.startswith(("https://", "http://")):
        return safe_url(value)
    return value


async def collect_controls(page, limit: int = 250) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    selectors = [
        ("button", "button"),
        ("link", "a"),
        ("treeitem", '[role="treeitem"]'),
        ("checkbox", 'input[type="checkbox"], [role="checkbox"]'),
        ("tab", '[role="tab"]'),
        ("button-role", '[role="button"]'),
    ]
    seen: set[str] = set()
    for kind, selector in selectors:
        locator = page.locator(selector)
        try:
            count = min(await locator.count(), limit)
        except Exception:
            continue
        for index in range(count):
            element = locator.nth(index)
            try:
                label = (await element.get_attribute("aria-label")) or (await element.inner_text(timeout=300))
                label = " ".join(label.split())[:240]
                if not label:
                    label = await element.get_attribute("title") or ""
                if not label:
                    continue
                identity = f"{kind}:{label}"
                if identity in seen:
                    continue
                seen.add(identity)
                controls.append({
                    "kind": kind,
                    "label": label,
                    "checked": await element.get_attribute("aria-checked"),
                    "href": safe_url(await element.get_attribute("href") or "") or None,
                })
            except Exception:
                continue
    return controls


async def inspect(investigation_id: str) -> dict[str, Any]:
    try:
        from playwright.async_api import Error as PlaywrightError, async_playwright
    except ImportError as error:
        raise RuntimeError(
            "Playwright is missing. Install the project dependencies with "
            "'python -m pip install -r requirements.txt'."
        ) from error

    page_url = f"https://psi.nasa.gov/physci/repo/data/investigations/{investigation_id}"
    requests_by_key: dict[str, dict[str, Any]] = {}
    network_errors: list[dict[str, str]] = []
    response_tasks: list[asyncio.Task] = []
    script_route_candidates: set[str] = set()

    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(channel="chrome", headless=True)
        except PlaywrightError:
            # Fall back to Playwright's bundled Chromium if system Chrome is not found.
            browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=False)
        page = await context.new_page()
        page.on("request", lambda request: requests_by_key.setdefault(
            f"{request.method}:{request.url}",
            {
                "method": request.method,
                "resource_type": request.resource_type,
                "url": safe_url(request.url),
                "status": None,
                "content_type": None,
            },
        ))

        async def record_response(response) -> None:
            request = response.request
            key = f"{request.method}:{request.url}"
            record = requests_by_key.setdefault(key, {
                "method": request.method,
                "resource_type": request.resource_type,
                "url": safe_url(request.url),
            })
            record["status"] = response.status
            content_type = response.headers.get("content-type", "")
            record["content_type"] = content_type
            if request.resource_type in {"xhr", "fetch"} and "json" in content_type.lower():
                try:
                    payload = sanitize_json(await response.json())
                    encoded = json.dumps(payload, ensure_ascii=False)
                    if len(encoded) <= 250_000:
                        record["json_body"] = payload
                    else:
                        record["json_body_excerpt"] = encoded[:250_000]
                        record["json_body_truncated"] = True
                except Exception as error:
                    record["json_body_error"] = str(error)[:300]
            if request.resource_type == "script" and "psi.nasa.gov" in urlsplit(request.url).hostname:
                try:
                    script_text = await response.text()
                    quoted_values = re.findall(r'''["']([^"']{1,300})["']''', script_text)
                    for value in quoted_values:
                        if re.search(r"geode|/ws/|api|investig|data.?files?|download|folders?|documents?", value, re.IGNORECASE):
                            script_route_candidates.add(value)
                except Exception:
                    pass

        page.on("response", lambda response: response_tasks.append(asyncio.create_task(record_response(response))))
        page.on("requestfailed", lambda request: network_errors.append({
            "resource_type": request.resource_type,
            "url": safe_url(request.url),
            "error": request.failure or "request failed",
        }))

        await page.goto(page_url, wait_until="domcontentloaded", timeout=90_000)
        try:
            await page.wait_for_load_state("networkidle", timeout=20_000)
        except Exception:
            pass

        # Expand the section if the page exposes its heading as a clickable control.
        section = page.get_by_text(re.compile(r"data\s+files\s+and\s+documents", re.IGNORECASE)).first
        if await section.count():
            try:
                await section.click(timeout=3_000)
                await page.wait_for_timeout(1_500)
            except Exception:
                pass

        # The file tree can load only after the section is expanded, so wait for
        # any newly observed JSON responses as well as the initial page requests.
        try:
            await page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:
            pass
        if response_tasks:
            await asyncio.gather(*response_tasks, return_exceptions=True)

        body_text = ""
        try:
            body_text = await page.locator("body").inner_text(timeout=10_000)
        except Exception:
            pass
        content_html = await page.content()
        script_sources = re.findall(
            r'<script[^>]+src=["\']([^"\']+)["\']',
            content_html,
            flags=re.IGNORECASE,
        )
        controls = await collect_controls(page)
        result = {
            "investigation_id": investigation_id,
            "requested_url": page_url,
            "final_url": safe_url(page.url),
            "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "title": await page.title(),
            "visible_text_characters": len(body_text),
            "visible_text": body_text[:30_000],
            "controls": controls,
            "script_sources": [safe_url(source) for source in script_sources[:100]],
            "network_requests": list(requests_by_key.values())[:500],
            "script_route_candidates": sorted(script_route_candidates)[:500],
            "network_errors": network_errors[:100],
            "files_downloaded": False,
        }
        await context.close()
        await browser.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect PSI's live investigation and file-browser UI; does not download files."
    )
    parser.add_argument("investigation_id", nargs="?", default="PSI-10")
    args = parser.parse_args()
    investigation_id = args.investigation_id.upper()
    if not PSI_ID_RE.fullmatch(investigation_id):
        raise SystemExit("Use an investigation ID such as PSI-10.")
    report = asyncio.run(inspect(investigation_id))
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / f"psi_browser_probe_{investigation_id}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Investigation: {investigation_id}")
    print(f"Visible text characters: {report['visible_text_characters']}")
    print(f"Controls observed: {len(report['controls'])}")
    print(f"Network requests observed: {len(report['network_requests'])}")
    print(f"JSON responses observed: {sum('json_body' in item for item in report['network_requests'])}")
    print("Files downloaded: no")
    print(f"Probe report: {output_path}")


if __name__ == "__main__":
    main()

