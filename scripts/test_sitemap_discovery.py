#!/usr/bin/env python3
import sys

sys.path.insert(0, "/opt/scrap")

from app.services.discovery_extractors import discover_sitemap_urls

base = sys.argv[1] if len(sys.argv) > 1 else "https://www.sotbit.ru/blog/"
urls = discover_sitemap_urls(
    base, timeout=30, user_agent="ScrapBot/1.0", max_urls=10, crawl_delay=0
)
print("count", len(urls))
for u, t in urls[:10]:
    print(u)
