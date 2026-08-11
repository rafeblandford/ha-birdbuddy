"""Backfill the pybirdbuddy API this fork needs, on the released version.

This file exists ONLY so the fork works against the published
``pybirdbuddy`` without waiting for a release. It is deliberately the single
point of difference between this fork and the upstream pull request, which
carries these changes in pybirdbuddy itself:

    https://github.com/jhansche/pybirdbuddy/pull/50

When that lands and ha-birdbuddy pins a release containing it, delete this
module and the one call to `apply()` in `__init__.py`. Nothing else changes.

Two gaps are filled:

1. `meFeed` selects only `id`/`createdAt` on `FeedItemNewPostcard`, so a
   postcard's own images never reach the client.
2. `FeedNode` has no accessor for that media once it does.
"""

from birdbuddy.feed import FeedNode
from birdbuddy.queries import me as _me

from .const import LOGGER

_ORIGINAL_FRAGMENT = """fragment NewPostcardFields on FeedItemNewPostcard {
  ...FeedItemFields
  __typename
}"""

_WIDENED_FRAGMENT = """fragment NewPostcardFields on FeedItemNewPostcard {
  ...FeedItemFields
  expiresAt
  hasVideoMedia
  mediaImageCount
  inferenceType
  inferenceExecutionMode
  inferenceConfidenceLevel
  reanalyzeAvailability
  mediaSpeciesNameAssignmentAvailability
  feeder {
    ... on FeederForOwner {
      id
      name
      __typename
    }
    ... on FeederForMember {
      id
      name
      __typename
    }
    __typename
  }
  medias {
    ...MediaFullFields
    __typename
  }
  __typename
}"""


def _widen_feed_query() -> bool:
    """Select a NewPostcard's media in the feed query."""
    if "inferenceExecutionMode" in _me.FEED:
        return True
    if _ORIGINAL_FRAGMENT not in _me.FEED:
        LOGGER.warning(
            "Could not widen the meFeed query: the NewPostcardFields fragment "
            "is not what this fork expects. Postcard media will be "
            "unavailable, and the recent visitor image will stay unknown. "
            "pybirdbuddy has probably changed - check whether the upstream "
            "fix has landed and this fork is no longer needed."
        )
        return False
    _me.FEED = _me.FEED.replace(_ORIGINAL_FRAGMENT, _WIDENED_FRAGMENT)
    return True


def _add_feed_node_accessors() -> None:
    """Add FeedNode.medias / .images / .feeder_id when absent."""
    if hasattr(FeedNode, "images"):
        return

    from datetime import datetime, timezone

    from birdbuddy.media import Media

    def _medias(self: FeedNode) -> list[Media]:
        return sorted(
            (Media(m) for m in self.get("medias") or []),
            key=lambda m: m.created_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

    def _images(self: FeedNode) -> list[Media]:
        return [m for m in self.medias if not m.is_video]

    def _feeder_id(self: FeedNode) -> str | None:
        return (self.get("feeder") or {}).get("id")

    FeedNode.medias = property(_medias)
    FeedNode.images = property(_images)
    FeedNode.feeder_id = property(_feeder_id)


def apply() -> None:
    """Make the installed pybirdbuddy look like the fixed one."""
    _widen_feed_query()
    _add_feed_node_accessors()
