#!/usr/bin/env python3
"""
Resource site scraper — search Chinese video sites for media resources.
Based on OmniBox Spider patterns (MacCMS, custom frontend, WordPress).

Usage:
  python3 scraper.py search "斗破苍穹"
  python3 scraper.py detail <source_id> <video_id>
  python3 scraper.py play <source_id> <play_id>
  python3 scraper.py sources                              # list known sources
"""

import argparse
import json
import sys

from sources import SOURCES, get_source, list_sources


def cmd_sources(args):
    """List available sources."""
    sources = list_sources()
    print(json.dumps(sources, ensure_ascii=False, indent=2))


def cmd_search(args):
    """Search across sources."""
    results = []

    if args.source:
        sources_to_search = [args.source]
    else:
        sources_to_search = [k for k in SOURCES.keys()]

    for src_id in sources_to_search:
        src = get_source(src_id)
        if not src:
            continue
        print(f"  搜索 {src.label} ...", file=sys.stderr)
        try:
            src_results = src.search(args.keyword, args.page or 1)
            results.extend(src_results)
            print(f"    {src.label}: {len(src_results)} 条结果", file=sys.stderr)
        except Exception as e:
            print(f"    {src.label}: 错误 - {e}", file=sys.stderr)

    output = {
        "keyword": args.keyword,
        "total": len(results),
        "results": results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_detail(args):
    """Get video detail from a source."""
    src = get_source(args.source)
    if not src:
        print(json.dumps({"error": f"Unknown source: {args.source}"}), file=sys.stderr)
        sys.exit(1)

    result = src.detail(args.video_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_play(args):
    """Extract play URLs."""
    src = get_source(args.source)
    if not src:
        print(json.dumps({"error": f"Unknown source: {args.source}"}), file=sys.stderr)
        sys.exit(1)

    urls = src.play(args.play_id, args.flag or "")
    output = {
        "source": args.source,
        "play_id": args.play_id,
        "total": len(urls),
        "urls": urls,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Video resource site scraper (OmniBox patterns)"
    )
    sub = parser.add_subparsers(dest="action", help="Action")

    p_sources = sub.add_parser("sources", help="List available sources")
    p_sources.set_defaults(func=cmd_sources)

    p_search = sub.add_parser("search", help="Search across sources")
    p_search.add_argument("keyword", help="Search keyword")
    p_search.add_argument("--source", "-s", help="Limit to specific source ID")
    p_search.add_argument("--page", "-p", type=int, default=1)
    p_search.set_defaults(func=cmd_search)

    p_detail = sub.add_parser("detail", help="Get video detail")
    p_detail.add_argument("source", help="Source ID")
    p_detail.add_argument("video_id", help="Video ID")
    p_detail.set_defaults(func=cmd_detail)

    p_play = sub.add_parser("play", help="Extract play URL")
    p_play.add_argument("source", help="Source ID")
    p_play.add_argument("play_id", help="Play ID or URL")
    p_play.add_argument("--flag", "-f", help="Line flag/source name")
    p_play.set_defaults(func=cmd_play)

    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
