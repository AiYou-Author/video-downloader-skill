"""
Custom frontend video site scraper.
Handles non-MacCMS sites with custom frontend routing:
  - Search:  /so.html?wd= or /search?k= or /query.html?wd=
  - Detail:  /detail/{id}.html or /intro/{id}.html
  - Play:    /play/{id}-{sid}-{nid}.html
  - Player:  player_aaaa, playSource, xgplayer, or direct m3u8 extraction

Patterns derived from OmniBox Spider实战 (LIBVIO, 毒舌, etc.)
"""

import re
import json
from urllib.parse import urljoin, quote
from .base import BaseSource


class CustomSource(BaseSource):
    """Scraper for custom frontend video sites."""

    def __init__(self, source_id, config):
        super().__init__(source_id, config)

    def search(self, keyword, page=1):
        """
        Search using the configured search_path template.
        Supports:
          - {keyword} placeholder
          - Multiple search URL patterns as fallback
        """
        results = []

        search_path = self.config.get("search_path", "/search?wd={keyword}")
        search_url = self._url(search_path.format(keyword=quote(keyword)))
        if page > 1:
            # Some sites use page in URL
            search_url = search_url.replace(
                f"wd={quote(keyword)}",
                f"wd={quote(keyword)}&page={page}"
            )

        resp = self._get(search_url)
        if not resp:
            return results

        soup = self._soup(resp.text)
        detail_pattern = re.compile(
            self.config.get("detail_pattern", r'/detail/(\d+)\.html')
        )

        # Try multiple selectors for video cards
        card_selectors = [
            ".stui-vodlist__box", ".module-item", ".myui-vodlist__box",
            ".video-item", ".movie-item", ".search-item", "li.vodlist_item",
            ".hl-vod-list li", ".hl-list-item", ".public-list-box .public-list-box",
            ".module-search-item", ".col-md-2", ".col-xs-4",
            ".search-results .item", ".result-item",
        ]

        items = []
        for sel in card_selectors:
            items = soup.select(sel)
            if items:
                break

        if not items:
            items = soup.select("li a[href]")

        seen_ids = set()
        for item in items:
            link = item.select_one("a[href]") if item.name != "a" else item
            if not link:
                continue
            href = link.get("href", "")

            m = detail_pattern.search(href)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen_ids:
                continue
            seen_ids.add(vid)

            # Get title
            title = ""
            title_el = (item.select_one(".title, .stui-vodlist__title, h4, .video-name, "
                                        ".movie-title, .hl-lc-item .hl-lc-title, "
                                        ".module-item-title, .module-item-caption, span.name")
                        or link.select_one("img") or link)
            if hasattr(title_el, "get_text"):
                title = title_el.get_text(strip=True)
            if not title:
                title = title_el.get("title", "") or title_el.get("alt", "")

            # Get pic
            pic = ""
            img_el = item.select_one("img")
            if img_el:
                pic = img_el.get("data-original") or img_el.get("data-src") or img_el.get("src", "")
                if pic and pic.startswith("/"):
                    pic = self._url(pic)

            # Get remarks
            remarks = ""
            remarks_el = item.select_one(".pic-text, .remarks, .vod_remarks, "
                                          ".module-item-note, .module-item-text, "
                                          ".hl-pic-text, .hl-lc-item-remarks")
            if remarks_el and hasattr(remarks_el, "get_text"):
                remarks = remarks_el.get_text(strip=True)

            results.append({
                "source": self.source_id,
                "source_label": self.label,
                "id": vid,
                "title": title,
                "pic": pic,
                "remarks": remarks,
                "url": self._url(href),
            })

        return results

    def detail(self, video_id):
        """
        Get video detail from custom frontend.
        Tries multiple URL patterns and DOM structures.
        """
        result = {
            "source": self.source_id,
            "source_label": self.label,
            "id": video_id,
            "title": "", "pic": "", "content": "",
            "play_sources": [],
        }

        # Try multiple detail URL patterns
        detail_patterns = [
            f"/detail/{video_id}.html",
            f"/intro/{video_id}.html",
            f"/voddetail/{video_id}.html",
            f"/vod/detail/id/{video_id}.html",
        ]

        html = None
        for path in detail_patterns:
            resp = self._get(self._url(path))
            if resp and resp.status_code == 200:
                html = resp.text
                break

        if not html:
            return result

        soup = self._soup(html)

        # Title
        for sel in ["h1", "h2", ".vod-title", ".detail-title", ".movie-title",
                     "title", ".stui-content__title", ".hl-detail-title"]:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                result["title"] = el.get_text(strip=True)
                break

        # Pic
        for sel in [".vod-pic img", ".detail-pic img", ".movie-pic img",
                     ".stui-content__thumb img", "img.thumbnail"]:
            el = soup.select_one(sel)
            if el:
                result["pic"] = el.get("src") or el.get("data-original") or ""
                if result["pic"]:
                    break

        # Content
        for sel in [".vod-content", ".detail-content", ".movie-desc",
                     ".stui-content__detail .desc", ".hl-detail-content .text",
                     "meta[name=description]"]:
            el = soup.select_one(sel)
            if el:
                content = el.get("content") if el.name == "meta" else el.get_text(strip=True)
                if content:
                    result["content"] = content[:500]
                    break

        # Play sources — multiple DOM structures from OmniBox references
        play_sources = []

        # Pattern A: stui-content__playlist (STUI theme)
        for head_el in soup.select(".stui-content__playlist, .stui-vodlist__head"):
            head_name = head_el.get_text(strip=True)
            # Find adjacent playlist
            playlist = head_el.find_next(class_=["stui-content__playlist", "playlist"])
            if not playlist:
                playlist = head_el.find_next("ul")
            if playlist:
                episodes = []
                for a in playlist.select("a[href]"):
                    href = a.get("href", "")
                    name = a.get_text(strip=True)
                    if href:
                        episodes.append({"name": name, "play_id": href})
                if episodes:
                    play_sources.append({"flag": head_name, "episodes": episodes})

        # Pattern B: module-tab + module-play-list (module theme)
        if not play_sources:
            for tab_content in soup.select(".module-play-list, .module-play-list-content"):
                episodes = []
                for a in tab_content.select("a[href]"):
                    href = a.get("href", "")
                    name = a.get_text(strip=True)
                    if name and href:
                        episodes.append({"name": name, "play_id": href})
                if episodes:
                    # Find tab title
                    tab_title = ""
                    tab_el = tab_content.find_previous(class_=["module-tab-item", "tab-item"])
                    if not tab_el:
                        tab_el = soup.select_one(".module-tab-item.active, .tab-item.active")
                    if tab_el:
                        tab_title = tab_el.get_text(strip=True)
                    play_sources.append({"flag": tab_title, "episodes": episodes})

        # Pattern C: playlist-panel + netdisk-panel (LIBVIO style)
        if not play_sources:
            for panel in soup.select(".playlist-panel, .netdisk-panel"):
                panel_title = ""
                title_el = panel.select_one("h3, .panel-title, .title")
                if title_el:
                    panel_title = title_el.get_text(strip=True)
                episodes = []
                for a in panel.select("a[href]"):
                    href = a.get("href", "")
                    name = a.get_text(strip=True)
                    if href:
                        episodes.append({"name": name, "play_id": href})
                if episodes:
                    play_sources.append({"flag": panel_title, "episodes": episodes})

        # Pattern D: Generic — look for any player link area
        if not play_sources:
            for player_area in soup.select(".player, .play-box, .play_url, #playlist, "
                                           ".hl-player-wrap"):
                episodes = []
                for a in player_area.select("a[href]"):
                    href = a.get("href", "")
                    name = a.get_text(strip=True)
                    if href:
                        episodes.append({"name": name, "play_id": href})
                if episodes:
                    play_sources.append({"flag": "", "episodes": episodes})

        result["play_sources"] = play_sources
        return result

    def play(self, play_id, flag=""):
        """
        Extract play URLs from a play page.
        Handles: player_aaaa, playSource, xgplayer config, direct m3u8/mp4.
        """
        urls = []

        if play_id.startswith("http") and (".m3u8" in play_id or ".mp4" in play_id):
            ext = "m3u8" if ".m3u8" in play_id else "mp4"
            return [{"name": flag or "直链", "url": play_id, "type": ext}]

        # Resolve URL
        if play_id.startswith("/"):
            url = self._url(play_id)
        elif play_id.startswith("http"):
            url = play_id
        else:
            url = self._url(f"/play/{play_id}.html")

        resp = self._get(url)
        if not resp:
            return urls

        html = resp.text

        # 1. Try player_aaaa (MacCMS / custom frontend)
        player = self._extract_player_aaaa(html)
        if player:
            player_url = player.get("url", "")
            if player_url:
                ext = "m3u8" if ".m3u8" in player_url else "mp4"
                urls.append({
                    "name": player.get("from", flag or "播放"),
                    "url": player_url,
                    "type": ext,
                    "encrypt": player.get("encrypt", 0),
                })
                return urls  # player_aaaa is authoritative if present

        # 2. Try playSource / xgplayer config
        ps = self._extract_play_source(html)
        if ps:
            ps_url = ps.get("src", "") or ps.get("url", "")
            if ps_url:
                ext = "m3u8" if ".m3u8" in ps_url else "mp4"
                urls.append({
                    "name": flag or "播放",
                    "url": ps_url,
                    "type": ext,
                })

        # 3. Try direct m3u8/mp4 links
        for ext, link in self._extract_m3u8_mp4_links(html):
            urls.append({"name": flag or ext, "url": link, "type": ext})

        # 4. Try magnet links
        for mag in self._extract_magnet_links(html):
            urls.append({"name": flag or "磁力", "url": mag, "type": "magnet"})

        return urls
