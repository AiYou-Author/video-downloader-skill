"""
Browser-based source scraper for SPA (React/Vue) video sites.
Uses Playwright for JS rendering, then falls back to normal HTML parsing.
"""

import re
import json
import httpx
from urllib.parse import urljoin, quote
from .base import BaseSource

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


class BrowserSource(BaseSource):
    """Scraper that uses Playwright to render JS-heavy SPA sites."""

    def __init__(self, source_id, config):
        super().__init__(source_id, config)
        self._browser = None
        self._context = None

    def _ensure_browser(self):
        if not HAS_PLAYWRIGHT:
            return None
        if self._browser is None:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
        return self._browser

    def _render_page(self, url, wait_selector=None, timeout=15000, capture_api=False):
        """Use Playwright to render a JS page and return HTML.
        If capture_api=True, also capture XHR/fetch JSON responses.
        """
        browser = self._ensure_browser()
        if not browser:
            resp = self._get(url)
            return resp.text if resp else ""
        try:
            page = browser.new_page()
            api_responses = []

            if capture_api:
                def _on_response(response):
                    try:
                        ct = response.headers.get("content-type", "")
                        if "json" in ct and response.status < 400:
                            body = response.json()
                            if isinstance(body, dict) and body.get("code") == 1:
                                api_responses.append({
                                    "url": response.url,
                                    "body": body,
                                })
                    except Exception:
                        pass
                page.on("response", _on_response)

            page.goto(url, timeout=timeout, wait_until="networkidle")
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=timeout)
                except Exception:
                    pass
            html = page.content()
            page.close()

            # Attach captured API data
            self._last_api_responses = api_responses
            return html
        except Exception:
            return ""

    def _render_and_soup(self, url, wait_selector=None, timeout=15000, capture_api=False):
        html = self._render_page(url, wait_selector, timeout, capture_api=capture_api)
        return self._soup(html) if html else None, html

    def _try_api_search(self, keyword, page=1):
        """Try to discover and call the site's hidden search API.
        Many SPA sites have /api/ or /vodsearch/ endpoints.
        """
        api_patterns = [
            f"/api.php/provide/vod/?ac=detail&wd={quote(keyword)}&pg={page}",
            f"/vodsearch/-------------.html?wd={quote(keyword)}&pg={page}",
            f"/index.php/vod/search.html?wd={quote(keyword)}&page={page}",
            f"/api/vod/search?wd={quote(keyword)}&page={page}",
            f"/api/search?keyword={quote(keyword)}&page={page}",
        ]
        for path in api_patterns:
            try:
                resp = self.client.get(self._url(path))
                if resp.status_code != 200:
                    continue
                data = resp.json() if "json" in resp.headers.get("content-type", "") else None
                if not data:
                    continue
                # MacCMS API format
                if data.get("code") == 1 and "list" in data:
                    return data["list"]
            except Exception:
                continue
        return None

    def search(self, keyword, page=1):
        """
        Search using a multi-strategy approach:
          1. Try API endpoints (fastest)
          2. Use Playwright to render search page
          3. Parse rendered HTML for results
        """
        results = []

        # Strategy 1: Try API endpoints
        api_results = self._try_api_search(keyword, page)
        if api_results:
            for item in api_results:
                vid = str(item.get("vod_id", ""))
                results.append({
                    "source": self.source_id,
                    "source_label": self.label,
                    "id": vid,
                    "title": item.get("vod_name", ""),
                    "pic": item.get("vod_pic", ""),
                    "remarks": item.get("vod_remarks", ""),
                    "year": item.get("vod_year", ""),
                    "type": item.get("type_name", ""),
                    "url": self._url(f"/voddetail/{vid}.html"),
                })
            return results

        # Strategy 2: Render with Playwright + capture API responses
        search_path = self.config.get("search_path", "/vodsearch/-------------.html?wd={keyword}")
        search_url = self._url(search_path.format(keyword=quote(keyword)))
        wait_sel = self.config.get("search_wait_selector", ".stui-vodlist__box, .module-item, "
                                    ".video-item, .movie-item, .search-item, a[href*='/voddetail/'], "
                                    "a[href*='/detail/'], a[href*='/movie/']")

        soup, html = self._render_and_soup(search_url, wait_sel, capture_api=True)

        # Check captured API responses first (fast path for SPA sites)
        api_responses = getattr(self, "_last_api_responses", [])
        for api_resp in api_responses:
            body = api_resp.get("body", {})
            items = body.get("list", []) or body.get("data", []) or []
            if isinstance(items, dict):
                items = items.get("list", []) or items.get("records", []) or []
            for item in items:
                vid = str(item.get("vod_id", item.get("id", item.get("movie_id", ""))))
                if not vid:
                    continue
                results.append({
                    "source": self.source_id,
                    "source_label": self.label,
                    "id": vid,
                    "title": item.get("vod_name", item.get("title", item.get("name", ""))),
                    "pic": item.get("vod_pic", item.get("pic", item.get("poster", ""))),
                    "remarks": item.get("vod_remarks", item.get("remarks", "")),
                    "year": str(item.get("vod_year", item.get("year", ""))),
                    "url": self._url(f"/voddetail/{vid}.html"),
                })
            if results:
                return results

        if soup is None and html:
            soup = self._soup(html)
        if not soup:
            return results

        detail_pattern = re.compile(
            self.config.get("detail_pattern", r'/voddetail/(\d+)\.html')
        )

        seen_ids = set()
        # Try multiple selectors
        for item in soup.select("a[href]"):
            href = item.get("href", "")
            m = detail_pattern.search(href)
            if not m:
                # Also try /detail/{id}.html, /movie/{id}
                m2 = re.search(r'/(?:detail|movie|vod)/(\w+)\.html', href)
                if m2:
                    m = m2
                else:
                    continue

            vid = m.group(1)
            if vid in seen_ids:
                continue
            seen_ids.add(vid)

            # Get parent card for metadata
            card = item.find_parent(["li", "div", "article"])
            if not card:
                card = item.parent

            title = item.get("title") or item.get_text(strip=True)
            pic = ""
            img = (card.select_one("img") if card else None) or item.select_one("img")
            if img:
                pic = img.get("data-original") or img.get("data-src") or img.get("src", "")

            remarks = ""
            if card:
                rm = card.select_one(".pic-text, .remarks, .module-item-note, span.badge")
                if rm:
                    remarks = rm.get_text(strip=True)

            results.append({
                "source": self.source_id,
                "source_label": self.label,
                "id": vid,
                "title": title[:100] if title else "",
                "pic": pic,
                "remarks": remarks,
                "url": self._url(href),
            })

        return results

    def detail(self, video_id):
        """Get video detail by rendering the detail page."""
        result = {
            "source": self.source_id,
            "source_label": self.label,
            "id": video_id,
            "title": "", "pic": "", "content": "",
            "play_sources": [],
        }

        # Try API first
        api_results = self._try_api_search("", 1)
        if api_results is None:
            try:
                resp = self.client.get(
                    self._url(f"/api.php/provide/vod/"),
                    params={"ac": "detail", "ids": video_id},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 1 and data.get("list"):
                        item = data["list"][0]
                        result["title"] = item.get("vod_name", "")
                        result["pic"] = item.get("vod_pic", "")
                        result["content"] = (item.get("vod_content", "") or "")[:500]

                        play_from = item.get("vod_play_from", "").split("$$$")
                        play_url = item.get("vod_play_url", "").split("$$$")
                        for flag, urls in zip(play_from, play_url):
                            episodes = []
                            for ep in urls.split("#"):
                                parts = ep.split("$")
                                if len(parts) >= 2:
                                    episodes.append({"name": parts[0], "play_id": parts[1]})
                            if episodes:
                                result["play_sources"].append({
                                    "flag": flag.strip(),
                                    "episodes": episodes,
                                })
                        return result
            except Exception:
                pass

        # Render detail page
        detail_paths = [
            f"/voddetail/{video_id}.html",
            f"/vod/detail/id/{video_id}.html",
            f"/detail/{video_id}.html",
        ]
        soup = None
        for path in detail_paths:
            soup, html = self._render_and_soup(
                self._url(path),
                wait_selector="a[href*='/play/'], a[href*='/vodplay/'], .playlist"
            )
            if soup:
                break

        if not soup:
            return result

        result |= self._parse_detail_soup(soup)
        return result

    def _parse_detail_soup(self, soup):
        """Parse detail page DOM for metadata and play sources."""
        result = {"play_sources": []}

        # Title
        for sel in ["h1", "h2", ".vod-title", ".detail-title", "title",
                     ".stui-content__title"]:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                result["title"] = el.get_text(strip=True)
                break

        # Pic
        for sel in [".vod-pic img", ".detail-pic img", "img.thumbnail"]:
            el = soup.select_one(sel)
            if el:
                result["pic"] = el.get("src") or el.get("data-original") or ""
                if result["pic"]:
                    break

        # Content
        for sel in [".vod-content", ".detail-content", ".movie-desc",
                     "meta[name=description]"]:
            el = soup.select_one(sel)
            if el:
                content = el.get("content") if el.name == "meta" else el.get_text(strip=True)
                if content:
                    result["content"] = content[:500]
                    break

        # Play sources — multi-strategy DOM parsing
        # A: stui-content__playlist
        for head in soup.select(".stui-content__playlist, .stui-vodlist__head"):
            head_name = head.get_text(strip=True)
            playlist = head.find_next(["ul", "div"])
            if playlist:
                episodes = []
                for a in playlist.select("a[href]"):
                    href = a.get("href", "")
                    if href:
                        episodes.append({"name": a.get_text(strip=True), "play_id": href})
                if episodes:
                    result["play_sources"].append({"flag": head_name, "episodes": episodes})

        # B: Generic playlist links
        if not result["play_sources"]:
            for area in soup.select(".playlist, .play_source, .play-box, "
                                    ".module-play-list, .player-list"):
                episodes = []
                for a in area.select("a[href]"):
                    href = a.get("href", "")
                    if href and ("/play/" in href or "/vodplay/" in href):
                        episodes.append({"name": a.get_text(strip=True), "play_id": href})
                if episodes:
                    result["play_sources"].append({"flag": "", "episodes": episodes})

        # C: All play links on page
        if not result["play_sources"]:
            episodes = []
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if re.search(r'/(play|vodplay)/', href):
                    episodes.append({"name": a.get_text(strip=True), "play_id": href})
            if episodes:
                result["play_sources"].append({"flag": "", "episodes": episodes})

        return result

    def play(self, play_id, flag=""):
        """Extract play URLs using Playwright for JS-rendered player pages."""
        urls = []

        if play_id.startswith("http") and (".m3u8" in play_id or ".mp4" in play_id):
            ext = "m3u8" if ".m3u8" in play_id else "mp4"
            return [{"name": flag or "直链", "url": play_id, "type": ext}]

        if play_id.startswith("/"):
            url = self._url(play_id)
        elif play_id.startswith("http"):
            url = play_id
        else:
            url = self._url(f"/vodplay/{play_id}.html")

        # Render page to get JS-populated player config
        html = self._render_page(url, wait_selector="video, iframe, script", timeout=15000)
        if not html:
            resp = self._get(url)
            html = resp.text if resp else ""

        # player_aaaa
        player = self._extract_player_aaaa(html)
        if player and player.get("url"):
            ext = "m3u8" if ".m3u8" in player["url"] else "mp4"
            return [{"name": player.get("from", flag or "播放"),
                     "url": player["url"], "type": ext,
                     "encrypt": player.get("encrypt", 0)}]

        # Direct links
        for ext, link in self._extract_m3u8_mp4_links(html):
            urls.append({"name": flag or ext, "url": link, "type": ext})

        # Magnets
        for mag in self._extract_magnet_links(html):
            urls.append({"name": flag or "磁力", "url": mag, "type": "magnet"})

        return urls

    def close(self):
        if self._browser:
            self._browser.close()
            self._playwright.stop()
            self._browser = None
