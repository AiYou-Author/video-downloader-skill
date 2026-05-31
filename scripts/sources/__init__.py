"""
Video source scrapers based on OmniBox Spider patterns.
Each source implements: search, detail, play.
"""
from .base import BaseSource
from .maccms import MacCMSSource
from .custom import CustomSource

# Source registry — add new sources here
SOURCES = {
    "libvio": {
        "class": CustomSource,
        "label": "LIBVIO",
        "base_url": "https://www.libvio.fun",
        "search_path": "/so.html?wd={keyword}",
        "detail_pattern": r'/detail/(\d+)\.html',
        "play_pattern": r'/play/(\d+)-(\d+)-(\d+)\.html',
    },
    # MacCMS-style sites — user can configure SITE_API env var
    "maccms": {
        "class": MacCMSSource,
        "label": "MacCMS",
        "note": "Set SITE_API env var to the target MacCMS API base URL",
    },
}


def get_source(source_id):
    """Get a source instance by ID."""
    cfg = SOURCES.get(source_id)
    if not cfg:
        return None
    cls = cfg["class"]
    return cls(source_id, cfg)


def list_sources():
    """List all available sources."""
    return {k: v.get("label") for k, v in SOURCES.items()}
