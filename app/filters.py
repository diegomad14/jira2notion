from typing import List
from .models import JiraIssue
import logging

logger = logging.getLogger(__name__)

def filter_issues_by_assignee(issues: List[JiraIssue], assignee: str) -> List[JiraIssue]:
    """Filter issues assigned to the user with the provided display name."""
    logger.info(f"Running filter for assignee: {assignee}")
    filtered_issues = [issue for issue in issues if issue.displayName.lower() == assignee.lower()]
    logger.info(f"Found {len(filtered_issues)} issues assigned to {assignee}")
    return filtered_issues
