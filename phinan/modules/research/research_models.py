"""Frontend data models for the Research module."""

from pydantic import BaseModel


class NewsItem(BaseModel):
    """News item model for frontend. Uses pydantic.BaseModel."""

    title: str = ""
    publisher: str = ""
    published: str = ""
    link: str = ""  # URL to article
    sentiment_label: str = "neutral"  # "positive", "negative", "neutral"
    sentiment_score: float = 0.5  # 0-1 confidence
    sentiment_score_fmt: str = "50%"  # Formatted percentage string
