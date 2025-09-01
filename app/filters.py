from typing import List
from .models import JiraIssue
import logging

logger = logging.getLogger(__name__)

def filter_issues_by_assignee(issues: List[JiraIssue], assignee: str) -> List[JiraIssue]:
    """Filter issues assigned to the user with the provided identifier.

    The identifier can be an email address or a display name. If the
    identifier contains an '@', the assignee email is used for
    comparison; otherwise the display name is used.
    """
    logger.info(f"Running filter for assignee: {assignee}")
    assignee_lower = assignee.lower()

    filtered_issues = []
    for issue in issues:
        email = (issue.emailAddress or "").lower()
        name = (issue.displayName or "").lower()
        if "@" in assignee_lower:
            if email == assignee_lower:
                filtered_issues.append(issue)
        else:
            if name == assignee_lower:
                filtered_issues.append(issue)

    logger.info(f"Found {len(filtered_issues)} issues assigned to {assignee}")
    return filtered_issues

