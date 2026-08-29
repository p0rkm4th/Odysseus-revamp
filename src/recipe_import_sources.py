"""Bounded, untrusted source acquisition for RecipeDraft preparation.

This module only obtains evidence.  It never creates or updates recipe state;
the existing InventoryService remains the sole commit owner.
"""

from __future__ import annotations

import asyncio
import json
async def fetch_recipe_source(url: str, *, owner: str) -> tuple[str, str | None]:
    """Return bounded source evidence and an optional failure message.

    YouTube uses the existing transcript adapter because a transcript is more
    useful recipe evidence than a generic page fetch.  Other URLs continue to
    use the existing public web-fetch tool.  Both outputs remain untrusted.
    """
    from src.youtube_handler import (
        extract_transcript_async, extract_video_metadata_async,
        extract_youtube_id, is_youtube_url,
    )

    if is_youtube_url(url):
        video_id = extract_youtube_id(url)
        if not video_id:
            return "", "The video URL could not be resolved for recipe review."
        transcript_result, metadata_result = await asyncio.gather(
            extract_transcript_async(url, video_id),
            extract_video_metadata_async(url),
        )
        evidence: list[str] = []
        if metadata_result.get("success"):
            title = str(metadata_result.get("title") or "").strip()
            description = str(metadata_result.get("description") or "").strip()
            if title:
                evidence.append(f"Video title: {title}")
            if description:
                evidence.append(f"Video description:\n{description}")
        if transcript_result.get("success"):
            transcript = str(transcript_result.get("transcript") or "").strip()
            if transcript:
                evidence.append(f"Video transcript:\n{transcript}")
        if not evidence:
            if metadata_result.get("success"):
                return "", "The video contained no recipe evidence for review."
            return "", "The video description and transcript are unavailable for recipe review."
        return "\n\n".join(evidence)[:12000], None

    from src.agent_tools.web_tools import WebFetchTool
    fetched = await WebFetchTool().execute(
        json.dumps({"url": url, "include_structured_data": True}), {"owner": owner}
    )
    if fetched.get("exit_code") != 0:
        return "", "The recipe source could not be fetched for review."
    return str(fetched.get("output") or "")[:12000], None
