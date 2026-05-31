"""
Base video source scraper.
Provides HTTP client, HTML parsing, and player URL extraction utilities.
"""

import re
import json
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin


class BaseSource:
    """Base class for video site scrapers."""

    def __init__(self, source_id, config):
        self.source_id = source_id
        self.label = config.get("label", source_id)
        self.base_url = config.get("base_url", "")
        self.config = config
        self.client = httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            timeout=15,
            follow_redirects=True,
            # Don't pick up env proxy settings (SOCKS etc.)
            proxy=None,
            trust_env=False,
        )

    def _url(self, path):
        return urljoin(self.base_url, path)

    def _get(self, url):
        try:
            resp = self.client.get(url)
            resp.raise_for_status()
            return resp
        except Exception as e:
            return None

    def _soup(self, html):
        return BeautifulSoup(html, "lxml")

    def _extract_player_aaaa(self, html):
        """Extract player_aaaa config from page JS.
        Common MacCMS/custom frontend pattern: player_aaaa = { ... }
        """
        # Match: player_aaaa = {...};  or var player_aaaa = {...};
        m = re.search(r'player_aaaa\s*=\s*(\{.+?\});', html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        return None

    def _extract_play_source(self, html):
        """Extract playSource / Player config from modern players (xgplayer, etc.)."""
        # playSource = { src: "...", type: "..." }
        m = re.search(r'(?:const|var|let)\s+playSource\s*=\s*(\{[^}]+\})', html)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        return None

    def _extract_m3u8_mp4_links(self, html):
        """Extract direct m3u8/mp4 links from page source."""
        urls = []
        # Direct m3u8
        for m in re.finditer(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html):
            urls.append(("m3u8", m.group(1)))
        # Direct mp4
        for m in re.finditer(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html):
            urls.append(("mp4", m.group(1)))
        return urls

    def _extract_magnet_links(self, html):
        """Extract magnet links from page."""
        magnets = []
        for m in re.finditer(r'(magnet:\?xt=urn:btih:[a-fA-F0-9]+[^\s"\'<>]*)', html):
            magnets.append(m.group(1))
        return magnets

    def search(self, keyword, page=1):
        """Search for videos. Returns list of {id, title, pic, remarks, year}."""
        raise NotImplementedError

    def detail(self, video_id):
        """Get video detail. Returns {title, pic, content, play_sources, ...}."""
        raise NotImplementedError

    def play(self, play_id):
        """Get play URL. Returns [{name, url, type}]."""
        raise NotImplementedError
