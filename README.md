# scraper-asos

Finds production scraper for **ASOS** (aggregator).

- Locale: English + EUR (`store=ROE`, `country=IE`, `currency=EUR`, `lang=en-GB`)
- Source: `scraper-asos`
- Catalog API: `https://www.asos.com/api/product/search/v2/categories/{cid}` via `curl_cffi` (Chrome impersonation)
- Embeddings: local SigLIP `google/siglip-base-patch16-384`
- CI: **parallel scrape → 60× embed matrix** (same architecture as scraper-kith / scraper-reserved)
- Schedule: Mon/Wed/Fri 06:17 UTC

```bash
python main.py --mode scrape
python main.py --mode embed --chunk 0 --total-chunks 10
python main.py --mode full   # single-process (not for CI)
```

Secrets: `SUPABASE_URL`, `SUPABASE_KEY` only.
