"""Bounded, untrusted source acquisition for RecipeDraft preparation.

This module only obtains evidence.  It never creates or updates recipe state;
the existing InventoryService remains the sole commit owner.
"""

from __future__ import annotations

import json
async def fetch_recipe_source(url: str, *, owner: str) -> tuple[str, str | None]:
    """Return bounded source evidence and an optional failure message.

    YouTube uses the existing transcript adapter because a transcript is more
    useful recipe evidence than a generic page fetch.  Other URLs continue to
    use the existing public web-fetch tool.  Both outputs remain untrusted.
    """
    from src.youtube_handler import extract_transcript_async, extract_youtube_id, is_youtube_url

    if is_youtube_url(url):
        video_id = extract_youtube_id(url)
        if not video_id:
            return "", "The video URL could not be resolved for recipe review."
        result = await extract_transcript_async(url, video_id)
        if not result.get("success"):
            return "", "The video transcript is unavailable for recipe review."
        transcript = str(result.get("transcript") or "").strip()
        if not transcript:
            return "", "The video transcript contained no recipe evidence."
        return transcript[:12000], None

    from src.agent_tools.web_tools import WebFetchTool
    fetched = await WebFetchTool().execute(
        json.dumps({"url": url, "include_structured_data": True}), {"owner": owner}
    )
    if fetched.get("exit_code") != 0:
        return "", "The recipe source could not be fetched for review."
    return str(fetched.get("output") or "")[:12000], None
