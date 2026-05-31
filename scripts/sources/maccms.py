"""
MacCMS site scraper.
Handles the standard MacCMS / AppleCMS video site pattern:
  - Search:  /vodsearch/wd/{keyword}.html or /vodsearch/-------------.html?wd=
  - Detail:  /voddetail/{id}.html
  - Play:    /vodplay/{id}-{sid}-{nid}.html
  - Player:  player_aaaa config or direct m3u8 extraction

Set env: SITE_API = https://example.com  (the MacCMS site base URL)
"""

import os
import re
import json
from urllib.parse import urljoin, quote
from .base import BaseSource


class MacCMSSource(BaseSource):
    """Scraper for MacCMS/AppleCMS-style video sites."""

    def __init__(self, source_id, config):
        # base_url from SITE_API env var
        config = dict(config)
        config["base_url"] = os.environ.get("SITE_API", config.get("base_url", ""))
        super().__init__(source_id, config)

    @property
    def api_url(self):
        return self.base_url

    def _api_get(self, params):
        """Call MacCMS API endpoint."""
        try:
            resp = self.client.get(
                self._url("/api.php/provide/vod/"),
                params=params,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def search(self, keyword, page=1):
        """
        MacCMS search patterns:
          - API:  /api.php/provide/vod/?ac=detail&wd=keyword
          - HTML: /vodsearch/wd/keyword.html
          - HTML: /vodsearch/-------------.html?wd=keyword
        """
        results = []

        # Try API first
        data = self._api_get({"ac": "detail", "wd": keyword, "pg": str(page)})
        if data and data.get("code") == 1:
            for item in data.get("list", []):
                results.append({
                    "source": self.source_id,
                    "source_label": self.label,
                    "id": str(item.get("vod_id", "")),
                    "title": item.get("vod_name", ""),
                    "pic": item.get("vod_pic", ""),
                    "remarks": item.get("vod_remarks", ""),
                    "year": item.get("vod_year", ""),
                    "type": item.get("type_name", ""),
                    "url": self._url(f"/voddetail/{item.get('vod_id', '')}.html"),
                })
            return results

        # Fallback: parse HTML search page
        search_url = self._url(f"/vodsearch/-------------.html?wd={quote(keyword)}&pg={page}")
        resp = self._get(search_url)
        if not resp:
            return results

        soup = self._soup(resp.text)
        for item in soup.select(".stui-vodlist__box, .module-item, .myui-vodlist__box, li"):
            link = item.select_one("a")
            if not link:
                continue
            href = link.get("href", "")
            if "/voddetail/" not in href and "/vod/detail/" not in href:
                continue
            vid = re.search(r'/vod(?:detail)?/(?:id/)?(\d+)\.html', href)
            if not vid:
                continue
            results.append({
                "source": self.source_id,
                "source_label": self.label,
                "id": vid.group(1),
                "title": item.select_one(".title, .stui-vodlist__title, h4") or {},
                "title_text": (item.select_one(".title, .stui-vodlist__title, h4") or {}).get_text(strip=True) if hasattr(item.select_one(".title, .stui-vodlist__title, h4"), "get_text") else "",
                "pic": (item.select_one("img") or {}).get("data-original") or (item.select_one("img") or {}).get("src", ""),
                "remarks": (item.select_one(".pic-text, .remarks") or {}),
                "url": self._url(href),
            })
            # Clean up
            if isinstance(results[-1]["title"], dict) or not results[-1]["title"]:
                results[-1]["title"] = results[-1].pop("title_text", results[-1]["title"])

        return results

    def detail(self, video_id):
        """
        MacCMS detail patterns:
          - /voddetail/{id}.html
          - /vod/detail/id/{id}.html
        Returns video detail with play sources.
        """
        result = {
            "source": self.source_id,
            "source_label": self.label,
            "id": video_id,
            "title": "",
            "pic": "",
            "content": "",
            "actor": "",
            "director": "",
            "year": "",
            "area": "",
            "lang": "",
            "remarks": "",
            "play_sources": [],
        }

        # Try API
        data = self._api_get({"ac": "detail", "ids": video_id})
        if data and data.get("code") == 1:
            item = data.get("list", [{}])[0]
            result["title"] = item.get("vod_name", "")
            result["pic"] = item.get("vod_pic", "")
            result["content"] = item.get("vod_content", "")[:500]
            result["actor"] = item.get("vod_actor", "")
            result["director"] = item.get("vod_director", "")
            result["year"] = item.get("vod_year", "")
            result["area"] = item.get("vod_area", "")
            result["lang"] = item.get("vod_lang", "")
            result["remarks"] = item.get("vod_remarks", "")

            # Parse play sources from API response
            play_from = item.get("vod_play_from", "").split("$$$")
            play_url = item.get("vod_play_url", "").split("$$$")
            for i, (flag, urls) in enumerate(zip(play_from, play_url)):
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

        # Fallback: parse HTML detail page
        for path in [f"/voddetail/{video_id}.html", f"/vod/detail/id/{video_id}.html"]:
            resp = self._get(self._url(path))
            if not resp:
                continue

            soup = self._soup(resp.text)

            result["title"] = (soup.select_one("h1.title, h2.title, .vod-title")
                                or soup.select_one("title"))
            if hasattr(result["title"], "get_text"):
                result["title"] = result["title"].get_text(strip=True)
            result["pic"] = (soup.select_one(".vod-pic img, .detail-pic img") or {}).get("src", "")

            # Parse play list
            for source_block in soup.select(".playlist, .play_source, .stui-content__playlist"):
                episodes = []
                for a in source_block.select("a"):
                    href = a.get("href", "")
                    name = a.get_text(strip=True)
                    if href:
                        episodes.append({"name": name, "play_id": href})
                if episodes:
                    result["play_sources"].append({
                        "flag": "",
                        "episodes": episodes,
                    })

            if result["play_sources"]:
                break

        return result

    def play(self, play_id, flag=""):
        """
        MacCMS play URL extraction.
        play_id can be:
          - Direct URL from detail API (m3u8/mp4)
          - /vodplay/{id}-{sid}-{nid}.html path
          - player_aaaa config page
        """
        urls = []

        # If play_id looks like a direct media URL
        if play_id.startswith("http") and (".m3u8" in play_id or ".mp4" in play_id):
            ext = "m3u8" if ".m3u8" in play_id else "mp4"
            return [{"name": flag or "直链", "url": play_id, "type": ext}]

        # If play_id is a page path
        if play_id.startswith("/"):
            url = self._url(play_id)
        elif play_id.startswith("http"):
            url = play_id
        else:
            # Assume it's a play ID needing URL construction
            url = self._url(f"/vodplay/{play_id}.html")

        resp = self._get(url)
        if not resp:
            return urls

        html = resp.text

        # Try player_aaaa config
        player = self._extract_player_aaaa(html)
        if player:
            player_url = player.get("url", "")
            if player_url:
                ext = "m3u8" if ".m3u8" in player_url else "mp4"
                urls.append({
                    "name": player.get("from", "播放"),
                    "url": player_url,
                    "type": ext,
                    "encrypt": player.get("encrypt", 0),
                })

        # Try direct m3u8/mp4 links in page
        for ext, link in self._extract_m3u8_mp4_links(html):
            urls.append({"name": flag or ext, "url": link, "type": ext})

        return urls
