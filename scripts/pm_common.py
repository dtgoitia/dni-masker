"""Helpers shared by the pm-* skill scripts.

Skill scripts import this module by adding the repo's top-level `scripts/`
directory to sys.path.
"""

import re
import unicodedata

SLUG_MAX_LEN = 50


def slugify(title: str) -> str:
    """Lowercase ASCII kebab-case, cut at a word boundary to SLUG_MAX_LEN chars."""
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    if len(slug) > SLUG_MAX_LEN:
        slug = slug[: SLUG_MAX_LEN + 1].rsplit("-", 1)[0]
    return slug
