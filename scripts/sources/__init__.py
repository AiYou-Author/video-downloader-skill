"""
Video source scrapers based on OmniBox Spider patterns.
Loads site list from sites.json — edit that file to add/remove sites.
"""
import json
from pathlib import Path
from .base import BaseSource
from .maccms import MacCMSSource
from .custom import CustomSource
from .browser import BrowserSource

SITES_FILE = Path(__file__).parent / "sites.json"

# Static template for MacCMS (requires SITE_API env var)
BUILTIN_SOURCES = {
    "maccms": {
        "class": MacCMSSource,
        "label": "MacCMS",
        "type": "maccms",
        "note": "Set SITE_API env var to the target MacCMS API base URL",
    },
}


def _load_sites():
    """Load sites from sites.json."""
    sources = dict(BUILTIN_SOURCES)
    if SITES_FILE.exists():
        with open(SITES_FILE) as f:
            data = json.load(f)
        for site_id, cfg in data.get("sites", {}).items():
            source_type = cfg.get("type", "custom")
            if source_type == "maccms":
                cls = MacCMSSource
            elif source_type == "browser":
                cls = BrowserSource
            else:
                cls = CustomSource
            sources[site_id] = {
                "class": cls,
                **cfg,
            }
    return sources


# Global registry, reloaded on each access
_sources_cache = None


def _get_sources():
    global _sources_cache
    if _sources_cache is None:
        _sources_cache = _load_sites()
    return _sources_cache


def reload_sources():
    """Reload sources from disk."""
    global _sources_cache
    _sources_cache = None
    return _get_sources()


def get_source(source_id):
    """Get a source instance by ID."""
    sources = _get_sources()
    cfg = sources.get(source_id)
    if not cfg:
        return None
    cls = cfg["class"]
    return cls(source_id, cfg)


def list_sources():
    """List all available sources (label only)."""
    return {
        k: v.get("label", k)
        for k, v in _get_sources().items()
    }


def list_sources_detail():
    """List sources with full config (no secrets)."""
    return {
        k: {
            "label": v.get("label", k),
            "type": v.get("type", v.get("class", {}).__name__),
            "base_url": v.get("base_url", ""),
            "note": v.get("note", ""),
        }
        for k, v in _get_sources().items()
    }
