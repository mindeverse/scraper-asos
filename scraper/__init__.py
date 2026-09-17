"""ASOS catalog scraper — product search v2 API via curl_cffi (Akamai bypass)."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urljoin

from curl_cffi import requests as cffi_requests

from config import MEN_CATEGORIES, WOMEN_CATEGORIES, cfg

logger = logging.getLogger(__name__)

_thread_local = threading.local()
_keystore_lock = threading.Lock()
_keystore_version: str | None = None


def _session() -> cffi_requests.Session:
    sess = getattr(_thread_local, "session", None)
    if sess is None:
        sess = cffi_requests.Session(impersonate=cfg.CURL_IMPERSONATE)
        sess.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-GB,en;q=0.9",
                "User-Agent": cfg.USER_AGENT,
                "Referer": "https://www.asos.com/",
                "Origin": "https://www.asos.com",
            }
        )
        _thread_local.session = sess
    return sess


def _discover_keystore() -> str:
    global _keystore_version
    if _keystore_version:
        return _keystore_version
    with _keystore_lock:
        if _keystore_version:
            return _keystore_version
        sess = _session()
        try:
            r = sess.get(
                "https://www.asos.com/?country=IE&currency=EUR&lang=en-GB",
                headers={"Accept": "text/html"},
                timeout=cfg.REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            found = set(
                re.findall(
                    r'keyStoreDataversion["\']?\s*[:=]\s*["\']([a-z0-9-]+)["\']',
                    r.text,
                    flags=re.I,
                )
            )
            found |= set(re.findall(r"keyStoreDataversion=([a-z0-9-]+)", r.text, flags=re.I))
            if found:
                _keystore_version = sorted(
                    found, key=lambda v: int(v.rsplit("-", 1)[-1]) if "-" in v else 0
                )[-1]
            else:
                _keystore_version = "7qyyrb1-46"
            logger.info("ASOS keyStoreDataversion=%s", _keystore_version)
        except Exception as e:
            logger.warning("keyStore discovery failed (%s); using fallback", e)
            _keystore_version = "7qyyrb1-46"
        return _keystore_version


def _money(amount: Any, currency: str | None = None) -> str | None:
    if amount is None:
        return None
    currency = currency or cfg.CURRENCY
    try:
        val = float(amount)
    except (TypeError, ValueError):
        return None
    return f"{val:.2f}{currency}"


def _abs_image(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    return "https://" + url.lstrip("/")


def _product_url(path: str) -> str:
    path = (path or "").split("#")[0].split("?")[0]
    if path.startswith("http"):
        return path
    return urljoin(cfg.BASE_URL + "/", path.lstrip("/"))


def _stable_id(product_url: str) -> str:
    digest = hashlib.sha256(f"{cfg.SOURCE}:{product_url}".encode()).hexdigest()[:24]
    return f"asos_{digest}"


def _detect_back(urls: list[str]) -> str | None:
    for u in urls:
        low = u.lower()
        if any(tok in low for tok in ("-back", "_back", "/back", "rear", "-bk", "_bk")):
            return u
    return None


def _parse_product(raw: dict[str, Any], category_slug: str, gender: str) -> dict[str, Any] | None:
    path = raw.get("url") or ""
    if not path:
        return None

    product_url = _product_url(path)
    title = (raw.get("name") or "").strip()
    if not title:
        return None

    image_url = _abs_image(raw.get("imageUrl"))
    if not image_url:
        return None

    extras_raw = raw.get("additionalImageUrls") or []
    extras = [_abs_image(u) for u in extras_raw if u]
    extras = [u for u in extras if u and u != image_url]

    back_image_url = _detect_back(extras)
    additional_images = ", ".join(extras) if extras else None

    price_obj = raw.get("price") or {}
    currency = price_obj.get("currency") or cfg.CURRENCY
    current = (price_obj.get("current") or {}).get("value")
    previous = (price_obj.get("previous") or {}).get("value")
    is_markdown = bool(price_obj.get("isMarkedDown"))

    if is_markdown and previous:
        price_str = _money(previous, currency)
        sale_str = _money(current, currency)
    else:
        price_str = _money(current, currency)
        sale_str = None

    brand = (raw.get("brandName") or cfg.BRAND_COLUMN or "ASOS").strip() or "ASOS"
    colour = (raw.get("colour") or "").strip()
    cat_display = category_slug.replace("-", " ").title()

    metadata = {
        "asos_id": raw.get("id"),
        "product_code": raw.get("productCode"),
        "colour_way_id": raw.get("colourWayId"),
        "colour": colour,
        "category_slug": category_slug,
        "is_selling_fast": raw.get("isSellingFast"),
        "is_new": raw.get("isNew"),
        "scraped_via": "asos-product-search-v2",
        "store": cfg.STORE,
        "country": cfg.COUNTRY,
        "currency": currency,
    }

    tags: list[str] = []
    if colour:
        tags.append(colour)
    if raw.get("isNew"):
        tags.append("new")
    if raw.get("isSellingFast"):
        tags.append("selling-fast")

    return {
        "id": _stable_id(product_url),
        "source": cfg.SOURCE,
        "product_url": product_url,
        "affiliate_url": None,
        "image_url": image_url,
        "compressed_image_url": None,
        "back_image_url": back_image_url,
        "brand": brand,
        "title": title,
        "description": None,
        "category": cat_display,
        "gender": gender,
        "price": price_str,
        "sale": sale_str,
        "metadata": json.dumps(metadata, ensure_ascii=False),
        "size": None,
        "second_hand": cfg.SECOND_HAND,
        "country": cfg.COUNTRY,
        "tags": tags or None,
        "additional_images": additional_images,
        "other": None,
    }


def _fetch_category(cid: int, slug: str, gender: str) -> list[dict[str, Any]]:
    sess = _session()
    keystore = _discover_keystore()
    products: list[dict[str, Any]] = []
    offset = 0
    page_size = cfg.PAGE_SIZE
    total = None

    while True:
        params = {
            "channel": "desktop-web",
            "country": cfg.COUNTRY,
            "currency": cfg.CURRENCY,
            "lang": cfg.LANG,
            "limit": str(page_size),
            "offset": str(offset),
            "store": cfg.STORE,
            "rowlength": "4",
            "keyStoreDataversion": keystore,
        }
        url = f"https://www.asos.com/api/product/search/v2/categories/{cid}"
        data = None
        for attempt in range(4):
            try:
                time.sleep(cfg.RATE_LIMIT_DELAY)
                resp = sess.get(url, params=params, timeout=cfg.REQUEST_TIMEOUT)
                if resp.status_code in (403, 429) or resp.status_code >= 500:
                    logger.warning(
                        "HTTP %s on cid=%s offset=%s attempt=%s",
                        resp.status_code,
                        cid,
                        offset,
                        attempt + 1,
                    )
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:
                logger.warning("cid=%s offset=%s attempt=%s err=%s", cid, offset, attempt + 1, e)
                time.sleep(2 ** attempt)
        if not data:
            logger.error("Giving up on cid=%s offset=%s", cid, offset)
            break

        if total is None:
            total = data.get("itemCount")
            logger.info("Category %s/%s cid=%s itemCount=%s", gender, slug, cid, total)

        batch = data.get("products") or []
        if not batch:
            break

        for raw in batch:
            parsed = _parse_product(raw, slug, gender)
            if parsed:
                products.append(parsed)

        offset += len(batch)
        if len(batch) < page_size:
            break
        if total is not None and offset >= total:
            break

    logger.info("Category %s/%s done: %d products", gender, slug, len(products))
    return products


def scrape_all_categories() -> list[dict[str, Any]]:
    """Scrape all configured ASOS categories; dedupe by product_url."""
    _discover_keystore()
    jobs: list[tuple[str, int, str]] = []
    for slug, cid in WOMEN_CATEGORIES:
        jobs.append((slug, cid, "Women"))
    for slug, cid in MEN_CATEGORIES:
        jobs.append((slug, cid, "Men"))

    seen: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=cfg.SCRAPE_WORKERS) as pool:
        futures = {
            pool.submit(_fetch_category, cid, slug, gender): (slug, cid, gender)
            for slug, cid, gender in jobs
        }
        for fut in as_completed(futures):
            slug, cid, gender = futures[fut]
            try:
                items = fut.result()
            except Exception as e:
                logger.error("Category failed %s/%s cid=%s: %s", gender, slug, cid, e)
                continue
            for p in items:
                url = p["product_url"]
                if url not in seen:
                    seen[url] = p
                else:
                    prev = seen[url]
                    if p.get("category") and p["category"] not in (prev.get("category") or ""):
                        prev["category"] = ", ".join(
                            filter(None, [prev.get("category"), p.get("category")])
                        )

    products = list(seen.values())
    logger.info("ASOS scrape complete: %d unique products", len(products))
    return products
