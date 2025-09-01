import asyncio
from .jira_client import get_new_issues, get_updated_issues
from .notion_client import create_or_update_notion_page, create_notion_page, update_notion_page
from .filters import filter_issues_by_assignee
from .logger_config import setup_logger
from .config import settings
from .notion_client import find_notion_page_by_ticket, set_notion_verified
from fastapi import HTTPException


logger = setup_logger()

async def process_updated_issues(last_key):
    """Process issues updated since the last recorded issue."""
    issues = await get_updated_issues()

    if not issues:
        logger.info("No new issues or updates.")
        return {"message": "No new updates."}
    
    last_processed_issue = None

    for issue in issues:
        issue_key = issue.key
        logger.info(f"Processing updated issue: {issue_key}")
        await create_or_update_notion_page(issue)
        last_processed_issue = issue_key

    return {"message": "Processed all updated issues.", "last_issue": last_processed_issue}

async def process_new_issues(last_processed_issue_key):
    try:
        logger.info("Starting check for new issues in Jira")
        issues = await get_new_issues()
        
        if issues:
            logger.info(f"Retrieved {len(issues)} new issues from Jira")
            filtered_issues = filter_issues_by_assignee(issues, settings.jira_assignee)
            
            if filtered_issues:
                latest_issue = filtered_issues[0]
                if latest_issue.key != last_processed_issue_key:
                    logger.info(f"New issue detected: {latest_issue.key}")
                    
                    await create_or_update_notion_page(latest_issue)
                    last_processed_issue_key = latest_issue.key
                    
                    logger.info(f"Notion page created or updated for issue: {latest_issue.key}")
                    return {"message": "New issue processed", "issue_key": latest_issue.key}
                else:
                    logger.info(f"No new issues assigned to {settings.jira_assignee}")
                    return {"message": "No new issues"}
            else:
                logger.info(f"No issues assigned to {settings.jira_assignee} in this update")
                return {"message": f"No issues assigned to {settings.jira_assignee} in this update"}
        else:
            logger.info("No new issues found in Jira")
            return {"message": "No new issues"}
    except Exception as e:
        logger.error(f"Error processing new issues: {e}")
        raise

async def periodic_task(last_processed_issue_key):
    while True:
        try:
            issues = await get_updated_issues()
            logger.info(f"Fetched {len(issues)} updated issues")
            filtered_issues = filter_issues_by_assignee(issues, settings.jira_assignee)
            
            if filtered_issues:
                latest_issue = filtered_issues[0]
                if latest_issue.key != last_processed_issue_key:
                    logger.info(f"New issue or update detected: {latest_issue.key}")

                    await create_or_update_notion_page(latest_issue)
                    last_processed_issue_key = latest_issue.key
                else:
                    logger.info("No new issues or updates.")
            else:
                logger.info(f"No issues assigned to {settings.jira_assignee}.")
        except Exception as e:
            logger.error(f"Error in periodic task: {e}")
        await asyncio.sleep(settings.check_interval)

async def sync_all_user_issues():
    try:
        logger.info("Starting full synchronization of issues assigned to the user")

        jql = (
            'assignee = currentUser() AND '
            'status IN ("To Do","In Progress","Impact Estimated","QUARANTINE",'
            '"Resolution In Progress","Routing","Waiting For Customer") '
            'ORDER BY updated DESC'
        )
        from .jira_client import _fetch_issues
        issues = await _fetch_issues(jql)

        if not issues:
            return {"message": "No issues assigned to this user."}

        processed_issues = []

        for issue in issues:
            issue_key = issue.key
            logger.info(f"Synchronizing issue: {issue_key}")

            existing_page = await find_notion_page_by_ticket(issue_key)

            if existing_page:
                logger.info(f"Updating status to 'Initial' for the existing page of {issue_key}")
                await set_notion_verified(existing_page, False)
                await update_notion_page(existing_page["id"], issue)
            else:
                logger.info(f"Creating new Notion page with status 'Initial' for {issue_key}")
                await create_notion_page(issue)

            processed_issues.append(issue_key)

        return {"message": f"Synchronized {len(processed_issues)} issues", "issues": processed_issues}

    except Exception as e:
        logger.error(f"Error in full synchronization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

