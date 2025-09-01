import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import os

JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)


def get_ticket_changelog(ticket_id: str):
    url = f"{JIRA_URL}{ticket_id}?expand=changelog"
    response = requests.get(url, auth=auth)
    
    if response.status_code != 200:
        print(f"DEBUG - Error en la respuesta de la API: {response.status_code}")
        return None

    changelog = response.json().get("changelog", {}).get("histories", [])
    if not changelog:
        print("DEBUG - No se encontró historial de cambios.")
        return None

    latest_change = None
    latest_change_time = None
    last_change_was_assignee = False

    for history in changelog:
        change_time = history.get("created")
        change_time = datetime.strptime(change_time, "%Y-%m-%dT%H:%M:%S.%f%z")

        if not latest_change_time or change_time > latest_change_time:
            for change in history.get("items", []):
                if change.get("field") == "assignee":
                    from_assignee = change.get('fromString', 'Unassigned') or 'Unassigned'
                    to_assignee = change.get('toString', 'Unassigned') or 'Unassigned'
                    
                    latest_change = {
                        'Assignee Change': 'Assignee Change',
                        'From': from_assignee,
                        'To': to_assignee
                    }
                    last_change_was_assignee = True
                else:
                    latest_change = {
                        'Field Change': change.get('field'),
                        'From': change.get('fromString', 'N/A'),
                        'To': change.get('toString', 'N/A')
                    }
            
            latest_change_time = change_time

    if not last_change_was_assignee:
        print("DEBUG - El último cambio no fue una asignación.")
        return None

    print(f"DEBUG - Último cambio detectado: {latest_change}")
    return latest_change
