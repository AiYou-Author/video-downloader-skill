#!/usr/bin/env python3
"""
Media Tool — 输入剧名/电影名，自动搜索并下载。
Usage:
  python3 media_tool.py download "斗破苍穹年番"         # 搜+自动下载
  python3 media_tool.py search "流浪地球2"              # 只看搜索结果
  python3 media_tool.py download "<URL>" --url           # 直接链接下载
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SCRAPER = BASE_DIR / "scraper.py"
DOWNLOADER = BASE_DIR / "downloader.py"


def cmd_search(args):
    """Search across all sources."""
    cmd = [sys.executable, str(SCRAPER), "search", args.keyword, "--count", str(args.count)]
    if args.deep:
        cmd.append("--deep")
    subprocess.run(cmd)


def cmd_download(args):
    """Search + auto-download, best effort."""
    if args.url or args.keyword.startswith("http"):
        # Direct URL download
        url = args.keyword
        print(f"下载链接: {url[:120]}", file=sys.stderr)
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
        subprocess.run(dl_args)
        return

    # Search + auto-download
    cmd = [
        sys.executable, str(SCRAPER), "download", args.keyword,
        "--format", args.format or "bestvideo[height<=1080]+bestaudio/best",
    ]
    if args.output_dir:
        cmd += ["--output-dir", args.output_dir]
    if args.audio_only:
        cmd += ["--audio-only"]
    if args.proxy:
        cmd += ["--proxy", args.proxy]
    if args.subtitles:
        cmd += ["--subtitles"]
    subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(description="搜剧下剧一站搞定")
    sub = parser.add_subparsers(dest="action", help="Action")

    p_search = sub.add_parser("search", help="搜索可下载资源")
    p_search.add_argument("keyword")
    p_search.add_argument("--count", "-n", type=int, default=10)
    p_search.add_argument("--deep", action="store_true")
    p_search.set_defaults(func=cmd_search)

    p_dl = sub.add_parser("download", help="搜索并自动下载")
    p_dl.add_argument("keyword")
    p_dl.add_argument("--url", action="store_true", help="keyword 是下载链接")
    p_dl.add_argument("--output-dir", "-o")
    p_dl.add_argument("--format", "-f")
    p_dl.add_argument("--audio-only", "-a", action="store_true")
    p_dl.add_argument("--subtitles", action="store_true")
    p_dl.add_argument("--proxy")
    p_dl.add_argument("--cookies")
    p_dl.set_defaults(func=cmd_download)

    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
