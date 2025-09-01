"""Data models used throughout the application."""

from typing import Any, TypedDict


class JiraIssue(TypedDict, total=False):
    """Minimal representation of a Jira issue returned by the API.

    All fields are optional to mirror the behaviour of the Jira API where any
    field may be missing depending on the JQL query.  When accessing these
    fields elsewhere in the code base, ``dict.get`` should be used to avoid
    ``KeyError`` exceptions.
    """

    key: str
    summary: str
    description_rest: str
    status: str
    created: str
    reporter: dict[str, Any]
    assignee: dict[str, Any]
    displayName: str
    emailAddress: str
    description_adv: Any

