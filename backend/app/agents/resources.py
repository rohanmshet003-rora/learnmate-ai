"""Learning Resource Agent — Stage 2 implementation.

Suggests curated learning resources for a given topic and level
using IBM Granite.

URL policy: Granite is prompted to supply only root/section URLs of
well-known platforms. Any URL that does not start with a recognised
trusted domain prefix is replaced with None so the frontend never
presents an invented deep-link as a real resource.
"""

import logging
import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)

# ── Trusted domain prefixes ───────────────────────────────────────────────────
# Only URLs whose netloc ends with one of these are kept.
# Deep invented paths are dropped (url → None) rather than shown as real links.
_TRUSTED_DOMAINS = {
    "coursera.org",
    "edx.org",
    "udemy.com",
    "udacity.com",
    "khanacademy.org",
    "youtube.com",
    "youtu.be",
    "github.com",
    "docs.python.org",
    "python.org",
    "numpy.org",
    "pandas.pydata.org",
    "scikit-learn.org",
    "tensorflow.org",
    "pytorch.org",
    "kaggle.com",
    "developer.ibm.com",
    "ibm.com",
    "w3schools.com",
    "mozilla.org",         # MDN
    "developer.mozilla.org",
    "freecodecamp.org",
    "realpython.com",
    "docs.fast.ai",
    "fast.ai",
    "deeplearning.ai",
    "mit.edu",
    "stanford.edu",
    "arxiv.org",
    "towardsdatascience.com",
    "medium.com",
    "datacamp.com",
    "leetcode.com",
    "hackerrank.com",
    "geeksforgeeks.org",
}


def _sanitise_url(raw_url: Any) -> Optional[str]:
    """Return the URL if its domain is trusted, otherwise None.

    Accepts only http/https URLs. Strips query strings and fragments
    so we never persist a fabricated deep path — only the origin is kept.
    """
    if not raw_url or not isinstance(raw_url, str):
        return None
    url = raw_url.strip()
    if not url or url in ("", "null", "None"):
        return None
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None
        netloc = parsed.netloc.lower().lstrip("www.")
        # Check if netloc ends with any trusted domain
        if any(netloc == d or netloc.endswith("." + d) for d in _TRUSTED_DOMAINS):
            # Return only scheme + netloc + path (drop query/fragment)
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
            return clean
    except Exception:
        pass
    return None


def _parse_response(raw: str) -> Dict[str, Any]:
    """Extract JSON from Granite's response text."""
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start: end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning("ResourceAgent: could not parse Granite response: %s", raw[:300])
    return {}


def _normalise_resources(raw_resources: List[Any]) -> List[Dict[str, Any]]:
    """Normalise resource dicts and sanitise URLs."""
    result = []
    for r in raw_resources:
        if not isinstance(r, dict):
            continue
        title = str(r.get("title", "")).strip()
        if not title:
            continue
        result.append(
            {
                "title": title,
                "description": str(r.get("description", "")).strip() or None,
                "url": _sanitise_url(r.get("url")),
                "provider": str(r.get("provider", "")).strip() or None,
            }
        )
    return result


class ResourceAgent(BaseAgent):
    name = "resource_agent"
    description = (
        "Finds and ranks learning resources (courses, articles, videos) "
        "relevant to a student's current learning step."
    )

    async def run(self, inputs: dict) -> dict:
        """Suggest learning resources for a topic with IBM Granite.

        Expected inputs:
            topic (str)
            level (str)        — beginner | intermediate | advanced
            preferences (dict) — optional

        Returns:
            topic (str)
            resources (list[dict])  — title, description, url|None, provider
            granite_used (bool)
        """
        topic: str = inputs.get("topic", "")
        level: str = inputs.get("level", "beginner")
        preferences: Dict[str, Any] = inputs.get("preferences", {})

        prefs_note = f"\nLearner preferences: {json.dumps(preferences)}" if preferences else ""

        prompt = (
            "You are a learning resource curator. "
            "Output ONLY a JSON object with no extra text.\n\n"
            f"Topic: {topic}\nLevel: {level}{prefs_note}\n\n"
            "Output this exact JSON structure:\n"
            '{"resources":['
            '{"title":"...","description":"...","url":"https://coursera.org","provider":"Coursera"}'
            "]}\n\n"
            "Rules:\n"
            "- 3 to 5 resources\n"
            "- url MUST be the root or section URL of a real, well-known platform "
            "(e.g. https://coursera.org, https://docs.python.org, https://youtube.com, "
            "https://kaggle.com, https://freecodecamp.org, https://khanacademy.org)\n"
            "- do NOT invent specific course paths — use only the platform root\n"
            "- description must explain what the resource covers"
        )

        raw, granite_used = await self.granite.generate_safe(
            prompt, max_new_tokens=500, temperature=0.3
        )

        parsed = _parse_response(raw) if granite_used else {}
        resources = _normalise_resources(parsed.get("resources", []))

        return {
            "topic": topic,
            "resources": resources,
            "granite_used": granite_used,
        }
