#!/usr/bin/env python3
"""
Multi-source media search.
Queries YouTube, Bilibili, and other platforms for videos matching a keyword.
"""

import argparse
import json
import sys

try:
    import yt_dlp
except ImportError:
    print(json.dumps({"error": "yt-dlp not installed"}))
    sys.exit(1)


def search_youtube(keyword, count=10):
    """Search YouTube via yt-dlp."""
    query = f"ytsearch{count}:{keyword}"
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            results = []
            for entry in (info.get("entries") or []):
                results.append({
                    "source": "youtube",
                    "id": entry.get("id"),
                    "title": entry.get("title"),
                    "url": entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}",
                    "duration": entry.get("duration"),
                    "uploader": entry.get("uploader"),
                    "view_count": entry.get("view_count"),
                })
            return results
    except Exception as e:
        return [{"source": "youtube", "error": str(e)}]


def search_bilibili(keyword, count=10):
    """Search Bilibili via yt-dlp."""
    query = f"bilisearch{count}:{keyword}"
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            results = []
            for entry in (info.get("entries") or []):
                results.append({
                    "source": "bilibili",
                    "id": entry.get("id"),
                    "title": entry.get("title"),
                    "url": entry.get("url") or f"https://www.bilibili.com/video/{entry.get('id')}",
                    "duration": entry.get("duration"),
                    "uploader": entry.get("uploader"),
                    "view_count": entry.get("view_count"),
                })
            return results
    except Exception as e:
        return [{"source": "bilibili", "error": str(e)}]


def search_generic(keyword, count=10):
    """Search across generic extractors (TikTok, Vimeo, etc.)."""
    # Use yt-dlp's generic search
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "default_search": "auto",
    }
    results = []
    for extractor in ["duckduckgo", "google"]:
        try:
            query = f"{extractor}:video {keyword}"
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(query, download=False)
                for entry in (info.get("entries") or [])[:count]:
                    results.append({
                        "source": extractor,
                        "id": entry.get("id"),
                        "title": entry.get("title"),
                        "url": entry.get("url") or entry.get("webpage_url", ""),
                        "duration": entry.get("duration"),
                    })
        except Exception:
            pass
    return results


def search_all(keyword, count=10, sources=None):
    """Search across all or specified sources."""
    if sources is None:
        sources = ["youtube", "bilibili"]

    all_results = []
    for src in sources:
        if src == "youtube":
            all_results.extend(search_youtube(keyword, count))
        elif src == "bilibili":
            all_results.extend(search_bilibili(keyword, count))

    return all_results


def main():
    parser = argparse.ArgumentParser(description="Search media across platforms")
    parser.add_argument("keyword", help="Search keyword")
    parser.add_argument("--count", "-n", type=int, default=10, help="Results per source")
    parser.add_argument("--sources", "-s", default="youtube,bilibili",
                        help="Comma-separated sources (youtube,bilibili)")
    parser.add_argument("--json", action="store_true", default=True,
                        help="Output JSON")
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",")]
    results = search_all(args.keyword, args.count, sources)

    output = {
        "keyword": args.keyword,
        "total": len(results),
        "results": results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
