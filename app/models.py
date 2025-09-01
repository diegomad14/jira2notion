"""Data models used throughout the application."""

from typing import Any

from pydantic import BaseModel, Extra, validator


class JiraIssue(BaseModel):
    """Representation of a Jira issue with dynamic fields allowed."""

    key: str
    summary: str

    class Config:
        extra = Extra.allow

    def get(self, item: str, default: Any = None) -> Any:
        """Provide dict-like access to dynamically added attributes."""
        return getattr(self, item, default)

    @validator("key", "summary")
    def _not_empty(cls, value: str) -> str:  # pylint: disable=no-self-argument
        if not value:
            raise ValueError("field must not be empty")
        return value

