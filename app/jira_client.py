import os
from pathlib import Path
from typing import Any

import httpx
import yaml

from pydantic import ValidationError

from .models import JiraIssue

JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_DOMAIN = os.getenv("JIRA_DOMAIN")

# Load Jira field to Notion property mapping
FIELD_MAP_PATH = Path(__file__).with_name("field_map.yaml")
with FIELD_MAP_PATH.open("r", encoding="utf-8") as f:
    FIELD_MAP: dict[str, str] = yaml.safe_load(f) or {}

# Jira "key" is always returned and should not be requested explicitly
FIELDS_NEEDED = [k for k in FIELD_MAP.keys() if k != "key"]

async def check_jira_connection() -> bool:
    """Verify the connection with Jira."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{JIRA_DOMAIN}/rest/api/3/serverInfo",
                auth=(JIRA_EMAIL, JIRA_API_TOKEN)
            )
            return response.status_code == 200
    except Exception:
        return False


def _compose_jql(project_key: str, base_jql: str, time_filter: str, default_order: str) -> str:
    """Build final JQL ensuring time filters precede any ORDER BY clause."""
    parts = [f"project = {project_key}"]
    order_clause = default_order

    if base_jql:
        lower = base_jql.lower()
        if " order by " in lower:
            query, order = base_jql.rsplit(" order by ", 1)
            parts.append(query.strip())
            order_clause = order.strip()
        else:
            parts.append(base_jql)

    parts.append(time_filter)
    return " AND ".join(parts) + f" ORDER BY {order_clause}"


async def get_new_issues(project_key: str, base_jql: str) -> list[JiraIssue]:
    """Fetch new tickets for the given project created in the last 3 minutes."""
    jql = _compose_jql(
        project_key,
        base_jql,
        'created >= "-3m"',
        "created DESC",
    )
    return await _fetch_issues(jql)


async def get_updated_issues(project_key: str, base_jql: str) -> list[JiraIssue]:
    """Fetch tickets for the given project updated in the last 3 minutes."""
    jql = _compose_jql(
        project_key,
        base_jql,
        'updated >= "-3m" AND created >= "-5d"',
        "updated DESC",
    )
    return await _fetch_issues(jql)


async def _fetch_issues(jql: str) -> list[JiraIssue]:
    url = f"{JIRA_DOMAIN}/rest/api/3/search"
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)

    issues_out: list[JiraIssue] = []
    start_at = 0
    max_results = 100

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                params = {
                    "jql": jql,
                    "fields": ",".join(FIELDS_NEEDED),
                    "startAt": start_at,
                    "maxResults": max_results,
                }

                resp = await client.get(
                    url,
                    params=params,
                    auth=auth,
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()

                for it in data.get("issues", []):
                    f = it.get("fields", {}) or {}
                    issue_data: dict[str, Any] = {"key": it.get("key")}

                    for field in FIELDS_NEEDED:
                        value = f.get(field)
                        if field == "status":
                            value = (value or {}).get("name") if isinstance(value, dict) else value
                        issue_data[field] = value

                    assignee: dict[str, Any] = issue_data.get("assignee") or {}
                    issue_data["displayName"] = assignee.get("displayName")
                    issue_data["emailAddress"] = assignee.get("emailAddress")

                    try:
                        issues_out.append(JiraIssue(**issue_data))
                    except ValidationError as err:
                        print(f"Skipping invalid issue {issue_data.get('key')}: {err}")

                start_at += max_results
                if start_at >= data.get("total", 0):
                    break

        print(f"Issues returned by Jira: {issues_out}")
    except Exception as e:
        print(f"Error querying Jira (search): {e}")

    return issues_out
