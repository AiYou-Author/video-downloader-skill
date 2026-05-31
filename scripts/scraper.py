#!/usr/bin/env python3
"""
Practical media search — find download links for any movie/show name.
Strategies: DDG web search for torrent/magnet → yt-dlp platform search.
"""

import argparse
import json
import re
import sys
import subprocess
from pathlib import Path
from urllib.parse import quote

try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    HAS_DDG = False

BASE_DIR = Path(__file__).resolve().parent


def search_web(keyword, max_results=10, proxy=None):
    """Search the web for download/torrent/magnet links."""
    results = []
    if not HAS_DDG:
        return results

    queries = [
        f"{keyword} 下载 magnet",
        f"{keyword} torrent download",
        f"{keyword} m3u8 mp4 在线",
    ]

    seen_urls = set()
    ddgs_kwargs = {}
    if proxy:
        ddgs_kwargs["proxy"] = proxy

    try:
        with DDGS(**ddgs_kwargs) as ddgs:
            for query in queries:
                try:
                    for r in ddgs.text(query, max_results=max(3, max_results // len(queries))):
                        url = r.get("href", "")
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        results.append({
                            "source": "web",
                            "source_label": "网页搜索",
                            "title": r.get("title", ""),
                            "url": url,
                            "body": r.get("body", "")[:300],
                        })
                except Exception:
                    continue
    except Exception:
        pass
    return results


def extract_links_from_page(url):
    """Quickly scan a URL for download links."""
    import httpx
    links = []
    try:
        with httpx.Client(timeout=10, follow_redirects=True, proxy=None, trust_env=False,
                          headers={"User-Agent": "Mozilla/5.0"}) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text

            # Magnet links
            for m in re.finditer(r'((?:magnet:\?xt=urn:btih:)[a-fA-F0-9]{32,}[^\s"\'<>]*)', html):
                links.append({"url": m.group(1), "type": "magnet", "from": url})

            # m3u8 links
            for m in re.finditer(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>,\]]*)', html):
                links.append({"url": m.group(1), "type": "m3u8", "from": url})

            # mp4 links
            for m in re.finditer(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>,\]\)]*)', html):
                links.append({"url": m.group(1), "type": "mp4", "from": url})

            # ed2k links
            for m in re.finditer(r'(ed2k://[^\s"\'<>]+)', html):
                links.append({"url": m.group(1), "type": "ed2k", "from": url})
    except Exception:
        pass
    return links


def cmd_search(args):
    """Search for downloadable media."""
    keyword = args.keyword
    print(f"搜索下载源: {keyword} ...", file=sys.stderr)

    all_results = []

    # 1. Web search for torrent/magnet/download pages
    if not args.skip_web:
        print("  [网页] 搜索磁力/下载页面...", file=sys.stderr)
        web_results = search_web(keyword, args.count)
        print(f"  [网页] 找到 {len(web_results)} 条网页", file=sys.stderr)
        all_results.extend(web_results)

    # 2. yt-dlp platform search (YouTube, Bilibili, etc.)
    if not args.skip_platforms:
        print("  [平台] 搜索 YouTube/Bilibili...", file=sys.stderr)
        search_script = BASE_DIR / "search.py"
        result = subprocess.run(
            [sys.executable, str(search_script), keyword,
             "--count", str(args.count),
             "--sources", "youtube,bilibili"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                platform_results = data.get("results", [])
                print(f"  [平台] 找到 {len(platform_results)} 条", file=sys.stderr)
                all_results.extend(platform_results)
            except json.JSONDecodeError:
                pass

    # 3. Deep scan: for web results, try to extract direct download links
    if args.deep and all_results:
        print("  [深度] 扫描下载链接...", file=sys.stderr)
        for r in all_results[:5]:
            url = r.get("url", "")
            if not url:
                continue
            links = extract_links_from_page(url)
            if links:
                r["download_links"] = links
                print(f"    找到 {len(links)} 个下载链接: {url[:80]}", file=sys.stderr)

    output = {
        "keyword": keyword,
        "total": len(all_results),
        "results": all_results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_download(args):
    """Search and auto-download the best match."""
    keyword = args.keyword

    # If it's a direct URL, download directly
    if args.url or keyword.startswith("http"):
        url = keyword
        dl_args = [sys.executable, str(BASE_DIR / "downloader.py"), "download", url]
        if args.output_dir:
            dl_args += ["--output-dir", args.output_dir]
        if args.format:
            dl_args += ["--format", args.format]
        if args.audio_only:
            dl_args += ["--audio-only"]
        if args.proxy:
            dl_args += ["--proxy", args.proxy]
        subprocess.run(dl_args)
        return

    print(f"搜索: {keyword}", file=sys.stderr)

    # Phase 1: Search everywhere
    # Web search for magnet/torrent
    web_results = search_web(keyword, 5) if not args.skip_web else []

    # Platform search
    platform_results = []
    if not args.skip_platforms:
        search_script = BASE_DIR / "search.py"
        result = subprocess.run(
            [sys.executable, str(search_script), keyword,
             "--count", "5", "--sources", "youtube,bilibili"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                platform_results = [
                    r for r in data.get("results", [])
                    if "error" not in r and r.get("url")
                ]
            except json.JSONDecodeError:
                pass

    # Phase 2: Try web results first — scan for direct download links
    download_url = None
    for wr in web_results:
        url = wr.get("url", "")
        if not url:
            continue
        print(f"  扫描: {url[:100]}", file=sys.stderr)
        links = extract_links_from_page(url)
        for link in links:
            if link["type"] in ("magnet", "m3u8", "mp4"):
                download_url = link["url"]
                print(f"  找到: [{link['type']}] {link['url'][:120]}", file=sys.stderr)
                break
        if download_url:
            break

    # Phase 3: Fall back to YouTube/Bilibili
    if not download_url and platform_results:
        best = platform_results[0]
        download_url = best.get("url") or best.get("webpage_url", "")
        title = best.get("title", keyword)
        print(f"  使用: [{best.get('source', '?')}] {title[:80]}", file=sys.stderr)

    if not download_url:
        print(f"未找到可下载链接: {keyword}", file=sys.stderr)
        sys.exit(1)

    # Phase 4: Download
    print(f"  开始下载: {download_url[:120]}", file=sys.stderr)
    dl_args = [sys.executable, str(BASE_DIR / "downloader.py"), "download", download_url]
    if args.output_dir:
        dl_args += ["--output-dir", args.output_dir]
    if args.format:
        dl_args += ["--format", args.format]
    if args.audio_only:
        dl_args += ["--audio-only"]
    if args.proxy:
        dl_args += ["--proxy", args.proxy]
    if args.subtitles:
        dl_args += ["--subtitles"]
    subprocess.run(dl_args)


def main():
    parser = argparse.ArgumentParser(
        description="Search and download media by name"
    )
    sub = parser.add_subparsers(dest="action", help="Action")

    p_search = sub.add_parser("search", help="Search for downloadable media")
    p_search.add_argument("keyword")
    p_search.add_argument("--count", "-n", type=int, default=10)
    p_search.add_argument("--deep", action="store_true", help="Deep scan: extract download links from web results")
    p_search.add_argument("--skip-web", action="store_true")
    p_search.add_argument("--skip-platforms", action="store_true")
    p_search.set_defaults(func=cmd_search)

    p_dl = sub.add_parser("download", help="Search + auto-download")
    p_dl.add_argument("keyword")
    p_dl.add_argument("--url", action="store_true", help="Keyword is a direct URL")
    p_dl.add_argument("--output-dir", "-o")
    p_dl.add_argument("--format", "-f", default="bestvideo[height<=1080]+bestaudio/best")
    p_dl.add_argument("--audio-only", "-a", action="store_true")
    p_dl.add_argument("--subtitles", action="store_true")
    p_dl.add_argument("--proxy")
    p_dl.add_argument("--skip-web", action="store_true")
    p_dl.add_argument("--skip-platforms", action="store_true")
    p_dl.set_defaults(func=cmd_download)

    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
