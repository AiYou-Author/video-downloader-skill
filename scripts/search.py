#!/usr/bin/env python3
"""
Multi-source media search via yt-dlp.
Supports: YouTube, Bilibili, Dailymotion, NicoNico, SoundCloud,
          Google Video, Yahoo, and more.
"""

import argparse
import json
import sys

try:
    import yt_dlp
except ImportError:
    print(json.dumps({"error": "yt-dlp not installed"}))
    sys.exit(1)


# Source registry: { source_id: { prefix, label, url_template, extract_flat } }
SOURCE_REGISTRY = {
    "youtube": {
        "prefix": "ytsearch",
        "label": "YouTube",
        "url_template": "https://www.youtube.com/watch?v={id}",
        "extract_flat": True,
    },
    "youtube_music": {
        "prefix": "ytsearch",
        "label": "YouTube Music",
        "url_template": "https://music.youtube.com/watch?v={id}",
        "extract_flat": True,
        "suffix": "music",
    },
    "bilibili": {
        "prefix": "bilisearch",
        "label": "Bilibili",
        "url_template": "https://www.bilibili.com/video/{id}",
        "extract_flat": True,
    },
    "dailymotion": {
        "prefix": "dailymotionsearch",
        "label": "Dailymotion",
        "url_template": "https://www.dailymotion.com/video/{id}",
        "extract_flat": True,
    },
    "nicovideo": {
        "prefix": "niconicosearch",
        "label": "NicoNico",
        "url_template": "https://www.nicovideo.jp/watch/{id}",
        "extract_flat": True,
    },
    "soundcloud": {
        "prefix": "scsearch",
        "label": "SoundCloud",
        "url_template": "",
        "extract_flat": True,
    },
    "googlevideo": {
        "prefix": "gvsearch",
        "label": "Google Video",
        "url_template": "",
        "extract_flat": True,
    },
    "yahoo": {
        "prefix": "yahooseach",
        "label": "Yahoo",
        "url_template": "",
        "extract_flat": True,
    },
}

# Groups for convenience
SOURCE_GROUPS = {
    "all": ["youtube", "bilibili", "dailymotion", "nicovideo", "soundcloud"],
    "video": ["youtube", "bilibili", "dailymotion", "nicovideo", "googlevideo"],
    "audio": ["youtube_music", "soundcloud"],
    "china": ["bilibili"],
    "global": ["youtube", "dailymotion", "nicovideo", "googlevideo"],
}


def search_source(source_id, keyword, count=10):
    """Search a single source."""
    cfg = SOURCE_REGISTRY.get(source_id)
    if not cfg:
        return [{"source": source_id, "error": f"Unknown source: {source_id}"}]

    suffix = f":{cfg['suffix']}" if cfg.get("suffix") else ""
    query = f"{cfg['prefix']}{count}:{keyword}{suffix}"

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    if cfg.get("extract_flat"):
        opts["extract_flat"] = True

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            results = []
            for entry in (info.get("entries") or []):
                vid_id = entry.get("id") or ""
                url_template = cfg.get("url_template", "")
                url = entry.get("url") or entry.get("webpage_url") or ""
                if not url and url_template and vid_id:
                    url = url_template.format(id=vid_id)

                results.append({
                    "source": source_id,
                    "source_label": cfg["label"],
                    "id": vid_id,
                    "title": entry.get("title"),
                    "url": url,
                    "duration": entry.get("duration"),
                    "uploader": entry.get("uploader") or entry.get("channel"),
                    "view_count": entry.get("view_count"),
                    "description": (entry.get("description") or "")[:200],
                })
            return results
    except Exception as e:
        err_msg = str(e)
        # Truncate long error messages
        if len(err_msg) > 300:
            err_msg = err_msg[:300] + "..."
        return [{"source": source_id, "source_label": cfg["label"], "error": err_msg}]


def resolve_sources(source_arg):
    """Resolve source names, including group names."""
    requested = [s.strip() for s in source_arg.split(",")]
    resolved = []
    for name in requested:
        if name in SOURCE_GROUPS:
            for s in SOURCE_GROUPS[name]:
                if s not in resolved:
                    resolved.append(s)
        elif name in SOURCE_REGISTRY:
            if name not in resolved:
                resolved.append(name)
        else:
            # Unknown — skip with warning
            print(f"Warning: unknown source/group '{name}', skipped", file=sys.stderr)
    return resolved


def search_all(keyword, count=10, sources=None):
    """Search across specified sources."""
    if sources is None:
        sources = list(SOURCE_GROUPS["global"]) + list(SOURCE_GROUPS["china"])

    all_results = []
    for src in sources:
        all_results.extend(search_source(src, keyword, count))
    return all_results


def main():
    parser = argparse.ArgumentParser(
        description="Search media across platforms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Sources:
  Individual:  """ + ", ".join(SOURCE_REGISTRY.keys()) + """
  Groups:
    all      — """ + ", ".join(SOURCE_GROUPS["all"]) + """
    video    — """ + ", ".join(SOURCE_GROUPS["video"]) + """
    audio    — """ + ", ".join(SOURCE_GROUPS["audio"]) + """
    china    — """ + ", ".join(SOURCE_GROUPS["china"]) + """
    global   — """ + ", ".join(SOURCE_GROUPS["global"]) + """

Examples:
  %(prog)s "流浪地球2"
  %(prog)s "Never Gonna Give You Up" --sources youtube,soundcloud
  %(prog)s "進撃の巨人" --sources nicovideo
  %(prog)s "周杰伦" --sources audio
        """,
    )
    parser.add_argument("keyword", help="Search keyword")
    parser.add_argument("--count", "-n", type=int, default=10, help="Results per source")
    parser.add_argument("--sources", "-s", default="youtube,bilibili,dailymotion",
                        help="Comma-separated source IDs or group names")
    args = parser.parse_args()

    sources = resolve_sources(args.sources)
    if not sources:
        print("No valid sources specified", file=sys.stderr)
        sys.exit(1)

    print(f"搜索 '{args.keyword}' 在: {', '.join(sources)} ...", file=sys.stderr)

    results = search_all(args.keyword, args.count, sources)

    # Separate errors from results
    valid = [r for r in results if "error" not in r]
    errors = [r for r in results if "error" in r]

    output = {
        "keyword": args.keyword,
        "sources_queried": sources,
        "total": len(valid),
        "errors": len(errors),
        "results": valid,
    }
    if errors:
        output["error_details"] = errors

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
