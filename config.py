"""ASOS scraper configuration — EN+EUR via IE/ROE storefront."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


# Pure top-level categories (gender-correct). Overlaps deduped by product URL.
WOMEN_CATEGORIES: list[tuple[str, int]] = [
    ("dresses", 8799),
    ("tops", 4169),
    ("jeans", 3630),
    ("trousers-leggings", 2640),
    ("coats-jackets", 2641),
    ("jumpers-cardigans", 2637),
    ("hoodies-sweatshirts", 11321),
    ("skirts", 2639),
    ("shorts", 9263),
    ("shoes", 4172),
    ("bags-purses", 8730),
    ("accessories", 4174),
    ("jewellery", 4175),
    ("lingerie-nightwear", 6046),
    ("jumpsuits-playsuits", 7618),
    ("swimwear-beachwear", 2238),
    ("sportswear", 26091),
    ("loungewear", 21867),
    ("suits-separates", 13632),
    ("co-ords", 19632),
    ("socks-tights", 7657),
    ("face-body", 1314),
]

MEN_CATEGORIES: list[tuple[str, int]] = [
    ("shirts", 3602),
    ("t-shirts-vests", 7616),
    ("jeans", 4208),
    ("trousers-chinos", 4910),
    ("jackets-coats", 3606),
    ("jumpers-cardigans", 7617),
    ("hoodies-sweatshirts", 5668),
    ("shorts", 7078),
    ("shoes-boots-trainers", 4209),
    ("bags", 9265),
    ("accessories", 4210),
    ("jewellery", 5034),
    ("swimwear", 13210),
    ("sportswear", 26090),
    ("loungewear", 18797),
    ("suits", 5678),
    ("polo-shirts", 4616),
    ("co-ords", 28291),
    ("underwear", 20317),
]


@dataclass
class Config:
    BRAND_NAME: str = "ASOS"
    SOURCE: str = "scraper-asos"
    BRAND_COLUMN: str = "ASOS"  # overridden per-product with brandName
    SECOND_HAND: bool = False
    LANDING_PAGE: str = "https://www.asos.com/?country=IE&currency=EUR&lang=en-GB"
    BASE_URL: str = "https://www.asos.com"
    CURRENCY: str = "EUR"
    COUNTRY: str = "IE"
    STORE: str = "ROE"
    LANG: str = "en-GB"

    SUPABASE_URL: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    SUPABASE_KEY: str = field(default_factory=lambda: os.getenv("SUPABASE_KEY", ""))

    EMBEDDING_MODEL: str = "google/siglip-base-patch16-384"
    EMBEDDING_DIM: int = 768
    EMBEDDING_VERSION: int = 2
    RATE_LIMIT_DELAY: float = 0.25
    BATCH_SIZE: int = 5  # fleet override — keep ≤5
    STALE_MISS_THRESHOLD: int = 2
    REQUEST_TIMEOUT: int = 45
    SCRAPE_WORKERS: int = 3
    DOWNLOAD_WORKERS: int = 30
    TEXT_EMBED_BATCH_SIZE: int = 32
    PAGE_SIZE: int = 200  # ASOS API max
    USER_AGENT: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    GENDER_DEFAULT: str = "Unisex"
    CURL_IMPERSONATE: str = "chrome131"


cfg = Config()
