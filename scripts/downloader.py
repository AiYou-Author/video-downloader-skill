#!/usr/bin/env python3
"""
Video Downloader — unified yt-dlp wrapper for the video-downloader skill.
Single-script entry point, outputs JSON results.
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print(json.dumps({"error": "yt-dlp not installed. Run: pip install yt-dlp"}))
    sys.exit(1)


def get_output_dir():
    return os.environ.get("VIDEO_DL_OUTPUT_DIR", str(Path.cwd() / "downloads"))


def get_proxy():
    return os.environ.get("VIDEO_DL_PROXY", None)


def get_cookies():
    return os.environ.get("VIDEO_DL_COOKIES_FILE", None)


def _arg(args, name, default=None):
    return getattr(args, name, None) or default


def build_opts(args):
    out_dir = _arg(args, "output_dir") or get_output_dir()
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    fmt = _arg(args, "format") or os.environ.get("VIDEO_DL_DEFAULT_FORMAT", None)

    # Template
    if _arg(args, "playlist"):
        tmpl = "%(playlist_title)s/%(playlist_index)02d - %(title)s.%(ext)s"
    else:
        tmpl = "%(title)s.%(ext)s"

    opts = {
        "outtmpl": str(Path(out_dir) / tmpl),
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook] if not _arg(args, "quiet") else [],
        "merge_output_format": _arg(args, "merge_output") or None,
    }

    if fmt:
        opts["format"] = fmt
    elif _arg(args, "audio_only"):
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": _arg(args, "audio_format") or "mp3",
            "preferredquality": str(_arg(args, "audio_quality") or 192),
        }]
    else:
        opts["format"] = "bestvideo+bestaudio/best"

    if _arg(args, "subtitles"):
        opts["writesubtitles"] = True
        opts["writeautomaticsub"] = True
        opts["subtitleslangs"] = _arg(args, "sub_langs").split(",") if _arg(args, "sub_langs") else ["all"]
        opts["embedsubs"] = _arg(args, "embed_subs")

    if _arg(args, "proxy"):
        opts["proxy"] = _arg(args, "proxy")
    elif get_proxy():
        opts["proxy"] = get_proxy()

    if _arg(args, "cookies"):
        opts["cookiefile"] = _arg(args, "cookies")
    elif get_cookies():
        opts["cookiefile"] = get_cookies()

    if _arg(args, "limit_rate"):
        opts["ratelimit"] = int(_arg(args, "limit_rate")) * 1024 * 1024

    if _arg(args, "dry_run"):
        opts["simulate"] = True

    if _arg(args, "playlist"):
        opts["noplaylist"] = False
        if _arg(args, "playlist_start"):
            opts["playliststart"] = _arg(args, "playlist_start")
        if _arg(args, "playlist_end"):
            opts["playlistend"] = _arg(args, "playlist_end")
    else:
        opts["noplaylist"] = True

    return opts


def progress_hook(d):
    if d["status"] == "downloading":
        pct = d.get("_percent_str", "N/A").strip()
        speed = d.get("_speed_str", "N/A").strip()
        eta = d.get("_eta_str", "N/A").strip()
        sys.stderr.write(f"\r  [{pct}] {speed}  ETA: {eta}    ")
        sys.stderr.flush()
    elif d["status"] == "finished":
        sys.stderr.write("\n")


def cmd_info(args):
    """Get video info without downloading."""
    opts = build_opts(args)
    opts["simulate"] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(args.url, download=False)
        if info is None:
            print(json.dumps({"error": "Failed to extract info"}))
            return
        # Flatten for JSON output
        result = {
            "title": info.get("title"),
            "duration": info.get("duration"),
            "duration_string": info.get("duration_string"),
            "uploader": info.get("uploader"),
            "upload_date": info.get("upload_date"),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "description": (info.get("description") or "")[:500],
            "webpage_url": info.get("webpage_url"),
            "extractor": info.get("extractor"),
            "thumbnail": info.get("thumbnail"),
            "width": info.get("width"),
            "height": info.get("height"),
            "formats_count": len(info.get("formats") or []),
        }
        # List available formats (summary)
        formats = info.get("formats") or []
        result["available_formats"] = [
            {
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "resolution": f.get("resolution"),
                "filesize": f.get("filesize"),
                "format_note": f.get("format_note"),
            }
            for f in formats[:20]
            if f.get("resolution") or f.get("format_note")
        ]

        if info.get("entries"):
            result["is_playlist"] = True
            result["playlist_count"] = len(info["entries"])
            result["entries"] = [
                {"title": e.get("title"), "duration": e.get("duration")}
                for e in info["entries"][:50]
            ]

        print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_download(args):
    """Download video(s)."""
    opts = build_opts(args)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(args.url, download=not args.dry_run)
        if info is None:
            print(json.dumps({"error": "Failed to extract info"}))
            return

        # Determine actual output path
        out_dir = args.output_dir or get_output_dir()
        tmpl = opts["outtmpl"]
        # Ask yt-dlp to prepare the filename
        filename = ydl.prepare_filename(info)

        result = {
            "title": info.get("title"),
            "duration_string": info.get("duration_string"),
            "uploader": info.get("uploader"),
            "extractor": info.get("extractor"),
            "output_dir": out_dir,
        }

        if info.get("entries"):
            result["is_playlist"] = True
            result["playlist_count"] = len(info["entries"])

        print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_formats(args):
    """List available formats for a URL."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "simulate": True,
    }
    proxy = args.proxy or get_proxy()
    if proxy:
        opts["proxy"] = proxy
    cookies = args.cookies or get_cookies()
    if cookies:
        opts["cookiefile"] = cookies

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(args.url, download=False)
        if info is None:
            print(json.dumps({"error": "Failed to extract info"}))
            return

        formats = info.get("formats") or []
        print(json.dumps({
            "title": info.get("title"),
            "duration_string": info.get("duration_string"),
            "formats": [
                {
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution"),
                    "fps": f.get("fps"),
                    "filesize": f.get("filesize"),
                    "filesize_approx": f.get("filesize_approx"),
                    "tbr": f.get("tbr"),
                    "vcodec": f.get("vcodec"),
                    "acodec": f.get("acodec"),
                    "format_note": f.get("format_note"),
                }
                for f in formats
            ]
        }, ensure_ascii=False, indent=2))


def cmd_check(args):
    """Check environment and tool versions."""
    result = {
        "python": sys.version,
        "yt_dlp_version": yt_dlp.version.__version__,
    }
    import shutil
    ffmpeg = shutil.which("ffmpeg")
    result["ffmpeg"] = ffmpeg
    result["output_dir"] = get_output_dir()
    proxy = get_proxy()
    if proxy:
        result["proxy"] = proxy
    cookies = get_cookies()
    if cookies:
        result["cookies_file"] = cookies
        result["cookies_exists"] = os.path.isfile(cookies)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Video Downloader via yt-dlp")
    sub = parser.add_subparsers(dest="action", help="Action")

    # info
    p_info = sub.add_parser("info", help="Get video info without downloading")
    p_info.add_argument("url", help="Video/playlist URL")
    p_info.add_argument("--proxy", help="Proxy URL")
    p_info.add_argument("--cookies", help="Cookies file path")
    p_info.set_defaults(func=cmd_info)

    # download
    p_dl = sub.add_parser("download", help="Download video(s)")
    p_dl.add_argument("url", help="Video/playlist URL")
    p_dl.add_argument("--output-dir", "-o", help="Output directory")
    p_dl.add_argument("--format", "-f", help="Format selector (e.g. 'best[height<=1080]')")
    p_dl.add_argument("--audio-only", "-a", action="store_true", help="Download audio only")
    p_dl.add_argument("--audio-format", default="mp3", help="Audio format (default: mp3)")
    p_dl.add_argument("--audio-quality", type=int, default=192, help="Audio bitrate in kbps")
    p_dl.add_argument("--subtitles", "-s", action="store_true", help="Download subtitles")
    p_dl.add_argument("--sub-langs", help="Subtitle languages, comma-separated")
    p_dl.add_argument("--embed-subs", action="store_true", help="Embed subtitles into video")
    p_dl.add_argument("--merge-output", help="Merge output format (e.g. mp4, mkv)")
    p_dl.add_argument("--playlist", action="store_true", help="Download as playlist")
    p_dl.add_argument("--playlist-start", type=int, help="Playlist start index")
    p_dl.add_argument("--playlist-end", type=int, help="Playlist end index")
    p_dl.add_argument("--proxy", help="Proxy URL")
    p_dl.add_argument("--cookies", help="Cookies file path")
    p_dl.add_argument("--limit-rate", type=float, help="Download rate limit in MB/s")
    p_dl.add_argument("--dry-run", action="store_true", help="Simulate only")
    p_dl.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output")
    p_dl.set_defaults(func=cmd_download)

    # formats
    p_fmt = sub.add_parser("formats", help="List available formats")
    p_fmt.add_argument("url", help="Video URL")
    p_fmt.add_argument("--proxy", help="Proxy URL")
    p_fmt.add_argument("--cookies", help="Cookies file path")
    p_fmt.set_defaults(func=cmd_formats)

    # check
    p_chk = sub.add_parser("check", help="Check environment")
    p_chk.set_defaults(func=cmd_check)

    args = parser.parse_args()
    if not args.action:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
