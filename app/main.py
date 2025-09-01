from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Dict, Any
import logging

from .issue_processor import process_updated_issues, process_new_issues, periodic_task
from .logger_config import setup_logger
from .config import settings
from .state_manager import StateManager

app = FastAPI(
    title="Jira2Notion Sync API",
    description="API for synchronizing tickets between Jira and Notion",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = setup_logger()
state = StateManager()

scheduler: AsyncIOScheduler = None


@app.get("/")
async def read_root() -> Dict[str, str]:
    """Basic endpoint to check service status."""
    return {"message": "Jira2Notion integration is running!"}


@app.post("/check-updated-issues")
async def check_updated_issues() -> JSONResponse:
    """
    Endpoint to verify and process updated issues in Jira.
    Uses the function that already checks for duplicates through the
    'create_or_update_notion_page' logic.
    """
    try:
        last_key = state.get_last_key()
        logger.info(f"Last processed issue: {last_key}")

        result = await process_updated_issues(last_key)

        if "issue_key" in result:
            state.update_last_key(result["issue_key"])
            logger.info(f"New last processed issue: {result['issue_key']}")

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Error in /check-updated-issues: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        )


@app.post("/check-new-issues")
async def check_new_issues() -> JSONResponse:
    """
    Endpoint to verify and process new issues in Jira.
    Uses the function that, through 'create_or_update_notion_page',
    avoids creating duplicate pages in Notion.
    """
    try:
        last_key = state.get_last_key()
        logger.info(f"Last processed issue: {last_key}")

        result = await process_new_issues(last_key)

        if "issue_key" in result:
            state.update_last_key(result["issue_key"])
            logger.info(f"New last processed issue: {result['issue_key']}")

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Error in /check-new-issues: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        )


@app.get("/status")
async def service_status() -> Dict[str, Any]:
    """
    Service status endpoint.
    Reports the connection with Jira and Notion, the last processed issue,
    and the next run time of the periodic task.
    """
    try:
        from .jira_client import check_jira_connection
        from .notion_client import check_notion_connection

        next_run = None
        if scheduler and scheduler.get_jobs():
            next_run = scheduler.get_jobs()[0].next_run_time.isoformat()

        return {
            "status": "running",
            "last_processed_issue": state.get_last_key(),
            "jira_connected": await check_jira_connection(),
            "notion_connected": await check_notion_connection(),
            "next_run": next_run,
        }
    except Exception as e:
        logger.error(f"Error in /status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error checking service status: {str(e)}"
        )


@app.on_event("startup")
async def startup_event():
    """Initial setup when starting the application"""
    global scheduler

    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        periodic_task,
        trigger="interval",
        seconds=settings.check_interval,
        args=[state.get_last_key()],
        id="periodic_task",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.start()

    logger.info("Service started successfully")
    logger.info(f"Check interval: {settings.check_interval} seconds")
    logger.info(f"Last processed issue: {state.get_last_key()}")


@app.on_event("shutdown")
async def shutdown_event():
    """Handle application shutdown"""
    global scheduler
    if scheduler:
        scheduler.shutdown()
    logger.info("Service stopped successfully")

from .issue_processor import sync_all_user_issues

@app.post("/sync-user-issues")
async def sync_user_issues():
    """
    Synchronizes all tickets assigned to the user configured in Jira
    with the Notion database:
    - Creates new pages if they do not exist.
    - Updates status to 'Initial' if they already exist.
    """
    return await sync_all_user_issues()

