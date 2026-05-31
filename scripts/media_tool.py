#!/usr/bin/env python3
"""
Media Tool — unified search + download pipeline.
Usage:
  python3 media_tool.py search "流浪地球2"
  python3 media_tool.py download "流浪地球2"           # search + auto-pick + download
  python3 media_tool.py download "流浪地球2" --source youtube --index 0
  python3 media_tool.py download "<URL>" --url           # direct URL download
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DOWNLOADER = BASE_DIR / "downloader.py"
SEARCH = BASE_DIR / "search.py"


def cmd_search(args):
    """Search for media across sources."""
    cmd = [sys.executable, str(SEARCH), args.keyword, "--count", str(args.count)]
    if args.sources:
        cmd += ["--sources", args.sources]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    data = json.loads(result.stdout)
    return data


def cmd_download(args):
    """Search and download, or download directly from URL."""
    if args.url:
        # Direct URL download — reachability check first
        print(f"检测链接可达性...", file=sys.stderr)
        probe_args = [sys.executable, str(DOWNLOADER), "info", args.keyword]
        if args.proxy:
            probe_args += ["--proxy", args.proxy]
        if args.cookies:
            probe_args += ["--cookies", args.cookies]
        probe = subprocess.run(probe_args, capture_output=True, text=True, timeout=30)
        if probe.returncode != 0:
            print(f"链接不可达: {probe.stderr[-200:]}", file=sys.stderr)
            sys.exit(1)
        try:
            info = json.loads(probe.stdout)
            if "error" in info:
                print(f"链接解析失败: {info['error']}", file=sys.stderr)
                sys.exit(1)
            print(f"可达 ✓  {info.get('title','')[:60]}  {info.get('duration_string','')}  {info.get('width','?')}x{info.get('height','?')}", file=sys.stderr)
        except json.JSONDecodeError:
            pass

        dl_args = [sys.executable, str(DOWNLOADER), "download", args.keyword]
        if args.output_dir:
            dl_args += ["--output-dir", args.output_dir]
        if args.format:
            dl_args += ["--format", args.format]
        if args.audio_only:
            dl_args += ["--audio-only"]
        if args.proxy:
            dl_args += ["--proxy", args.proxy]
        if args.cookies:
            dl_args += ["--cookies", args.cookies]
        if args.subtitles:
            dl_args += ["--subtitles"]
        if args.quiet:
            dl_args += ["--quiet"]
        subprocess.run(dl_args)
        return

    # Search first
    print(f"搜索: {args.keyword} ...", file=sys.stderr)
    search_result = cmd_search(args)

    results = search_result.get("results", [])
    if not results:
        print(f"未找到与 '{args.keyword}' 相关的结果", file=sys.stderr)
        sys.exit(1)

    # Filter by source if specified
    if args.source:
        results = [r for r in results if r.get("source") == args.source]
        if not results:
            print(f"来源 '{args.source}' 没有匹配结果", file=sys.stderr)
            sys.exit(1)

    # Filter errors
    valid_results = [r for r in results if "error" not in r]
    if not valid_results:
        print("所有搜索源均返回错误", file=sys.stderr)
        sys.exit(1)

    # Auto-pick or use specified index
    if args.index is not None:
        if args.index >= len(valid_results):
            print(f"索引 {args.index} 超出范围 (共 {len(valid_results)} 个结果)", file=sys.stderr)
            sys.exit(1)
        target = valid_results[args.index]
    else:
        # Auto-pick: first result from preferred source
        # Prefer in order: youtube > bilibili > dailymotion > nicovideo > any
        preference = ["youtube", "bilibili", "dailymotion", "nicovideo"]
        target = None
        for src in preference:
            src_results = [r for r in valid_results if r.get("source") == src]
            if src_results:
                target = src_results[0]
                break
        if target is None:
            target = valid_results[0]

    title = target.get("title", "Unknown")
    url = target.get("url") or target.get("webpage_url", "")
    source = target.get("source", "unknown")

    if not url:
        print("错误: 无法获取下载链接", file=sys.stderr)
        sys.exit(1)

    print(f"\n选中: [{source}] {title}", file=sys.stderr)
    print(f"链接: {url}", file=sys.stderr)

    # Reachability check before download
    print(f"检测链接可达性...", file=sys.stderr)
    probe_args = [sys.executable, str(DOWNLOADER), "info", url]
    if args.proxy:
        probe_args += ["--proxy", args.proxy]
    if args.cookies:
        probe_args += ["--cookies", args.cookies]
    probe = subprocess.run(probe_args, capture_output=True, text=True, timeout=30)
    if probe.returncode != 0:
        print(f"链接不可达或无法解析: {probe.stderr[-200:]}", file=sys.stderr)
        sys.exit(1)
    try:
        info = json.loads(probe.stdout)
        if "error" in info:
            print(f"链接解析失败: {info['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"可达 ✓  时长: {info.get('duration_string','?')}  画质: {info.get('width','?')}x{info.get('height','?')}", file=sys.stderr)
    except json.JSONDecodeError:
        pass
    print(file=sys.stderr)

    # Download
    dl_args = [sys.executable, str(DOWNLOADER), "download", url]
    if args.output_dir:
        dl_args += ["--output-dir", args.output_dir]
    if args.format:
        dl_args += ["--format", args.format]
    if args.audio_only:
        dl_args += ["--audio-only"]
    if args.proxy:
        dl_args += ["--proxy", args.proxy]
    if args.cookies:
        dl_args += ["--cookies", args.cookies]
    if args.subtitles:
        dl_args += ["--subtitles"]
    if args.quiet:
        dl_args += ["--quiet"]

    subprocess.run(dl_args)


def cmd_info(args):
    """Show info about a URL or search result."""
    if args.url:
        cmd = [sys.executable, str(DOWNLOADER), "info", args.keyword]
    else:
        # Search first
        search_result = cmd_search(args)
        results = search_result.get("results", [])
        valid_results = [r for r in results if "error" not in r]
        if not valid_results:
            print("无结果", file=sys.stderr)
            sys.exit(1)
        url = valid_results[0].get("url", "")
        if not url:
            print("无法获取链接", file=sys.stderr)
            sys.exit(1)
        cmd = [sys.executable, str(DOWNLOADER), "info", url]

    if args.proxy:
        cmd += ["--proxy", args.proxy]
    if args.cookies:
        cmd += ["--cookies", args.cookies]
    subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(
        description="Media Tool — search and download videos by name"
    )
    sub = parser.add_subparsers(dest="action", help="Action")

    # search
    p_search = sub.add_parser("search", help="Search for media")
    p_search.add_argument("keyword", help="Search keyword")
    p_search.add_argument("--count", "-n", type=int, default=10, help="Results per source")
    p_search.add_argument("--sources", "-s", default="youtube,bilibili,dailymotion",
                          help="Sources (IDs or group names: all, video, audio, china, global)")
    p_search.set_defaults(func=lambda a: cmd_search(a) and None)

    # download
    p_dl = sub.add_parser("download", help="Search and download, or download from URL")
    p_dl.add_argument("keyword", help="Search keyword or URL (use --url flag for URL)")
    p_dl.add_argument("--url", action="store_true", help="Treat keyword as direct URL")
    p_dl.add_argument("--source", "-s", help="Filter source (youtube, bilibili)")
    p_dl.add_argument("--index", "-i", type=int, help="Pick result by index (0-based)")
    p_dl.add_argument("--output-dir", "-o", help="Output directory")
    p_dl.add_argument("--format", "-f", help="Format selector")
    p_dl.add_argument("--audio-only", "-a", action="store_true", help="Audio only")
    p_dl.add_argument("--subtitles", action="store_true", help="Download subtitles")
    p_dl.add_argument("--proxy", help="Proxy URL")
    p_dl.add_argument("--cookies", help="Cookies file")
    p_dl.add_argument("--quiet", "-q", action="store_true", help="Suppress output")
    p_dl.set_defaults(func=cmd_download)

    # info (search + show info)
    p_info = sub.add_parser("info", help="Show info for search result or URL")
    p_info.add_argument("keyword", help="Search keyword or URL")
    p_info.add_argument("--url", action="store_true", help="Treat keyword as direct URL")
    p_info.add_argument("--count", "-n", type=int, default=5)
    p_info.add_argument("--sources", default="youtube,bilibili")
    p_info.add_argument("--proxy", help="Proxy URL")
    p_info.add_argument("--cookies", help="Cookies file")
    p_info.set_defaults(func=cmd_info)

    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
