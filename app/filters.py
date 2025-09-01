from typing import List
from .models import JiraIssue
import logging

logger = logging.getLogger(__name__)

def filter_issues_by_assignee(issues: List[JiraIssue], assignee: str) -> List[JiraIssue]:
    """
    Filtra los issues asignados al usuario con el display name proporcionado.
    """
    logger.info(f"Ejecutando filtro para el asignado: {assignee}")
    filtered_issues = [issue for issue in issues if issue.displayName.lower() == assignee.lower()]
    logger.info(f"Se encontraron {len(filtered_issues)} issues asignados a {assignee}")
    return filtered_issues