import os
import httpx
from .models import JiraIssue

JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_DOMAIN = os.getenv("JIRA_DOMAIN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")

FIELDS_NEEDED = [
    "summary",
    "status",
    "assignee",
    "reporter",
    "created",
    "description",
    "customfield_12286",
]

async def check_jira_connection() -> bool:
    """Verifica la conexión con Jira."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{JIRA_DOMAIN}/rest/api/3/serverInfo",
                auth=(JIRA_EMAIL, JIRA_API_TOKEN)
            )
            return response.status_code == 200
    except Exception:
        return False


async def get_new_issues() -> list[JiraIssue]:
    """
    Obtiene tickets nuevos creados en los últimos 3 minutos.
    """
    jql = f'project = {JIRA_PROJECT_KEY} AND created >= "-3m" ORDER BY created DESC'
    return await _fetch_issues(jql)


async def get_updated_issues() -> list[JiraIssue]:
    """
    Obtiene tickets actualizados en los últimos 3 minutos (limitado a últimos 5 días).
    """
    jql = (
        f'project = {JIRA_PROJECT_KEY} AND updated >= "-3m" AND created >= "-5d" '
        'AND status IN ("Impact Estimated","QUARANTINE","Resolution In Progress","Routing","Waiting For Customer") '
        'ORDER BY updated DESC'
    )
    return await _fetch_issues(jql)


async def _fetch_issues(jql: str) -> list[JiraIssue]:
    url = f"{JIRA_DOMAIN}/rest/api/3/search/jql"
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)

    FIELDS_NEEDED = [
        "summary", "status", "assignee", "reporter", "created",
        "description", "customfield_12286",
    ]

    issues_out: list[JiraIssue] = []
    next_page_token = None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                body = {
                    "jql": jql,
                    "fields": FIELDS_NEEDED,
                }
                if next_page_token:
                    body["nextPageToken"] = next_page_token

                resp = await client.post(url, json=body, auth=auth,
                                         headers={"Accept": "application/json",
                                                  "Content-Type": "application/json"})
                resp.raise_for_status()
                data = resp.json()

                for it in data.get("issues", []):
                    f = it.get("fields", {}) or {}
                    assignee = f.get("assignee")
                    reporter = f.get("reporter")

                    issues_out.append(JiraIssue(
                        key=it.get("key"),
                        summary=f.get("summary", "") or "",
                        description_rest=str(f.get("customfield_12286") or ""),
                        status=(f.get("status") or {}).get("name", "") or "",
                        displayName=(assignee or {}).get("displayName"),
                        reporter=reporter,
                        created=f.get("created"),
                        description_adv=f.get("description"),
                    ))

                next_page_token = data.get("nextPageToken")
                if not next_page_token:
                    break

        print(f"Issues devueltos por Jira: {issues_out}")
    except Exception as e:
        print(f"Error al consultar Jira (search/jql): {e}")

    return issues_out
