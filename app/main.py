from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Dict, Any

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
    Uses the function that already performs duplicate verification through
    the 'create_or_update_notion_page' logic.
    """
    try:
        results: dict[str, Any] = {}
        for project in settings.projects:
            last_key = state.get_last_key(project.key)
            logger.info(f"Last processed issue for {project.key}: {last_key}")

            result = await process_updated_issues(project, last_key)

            if "last_issue" in result:
                state.update_last_key(project.key, result["last_issue"])
                logger.info(
                    f"New last processed issue for {project.key}: {result['last_issue']}"
                )

            results[project.key] = result

        return JSONResponse(content=results)

    except Exception as e:
        logger.error(f"Error in /check-updated-issues: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        )


@app.post("/check-new-issues")
async def check_new_issues() -> JSONResponse:
    """
    Endpoint to verify and process new issues in Jira.
    It uses the function that, through 'create_or_update_notion_page',
    avoids creating duplicate pages in Notion.
    """
    try:
        results: dict[str, Any] = {}
        for project in settings.projects:
            last_key = state.get_last_key(project.key)
            logger.info(f"Last processed issue for {project.key}: {last_key}")

            result = await process_new_issues(project, last_key)

            if "issue_key" in result:
                state.update_last_key(project.key, result["issue_key"])
                logger.info(
                    f"New last processed issue for {project.key}: {result['issue_key']}"
                )

            results[project.key] = result

        return JSONResponse(content=results)

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
    and the next scheduled time for the periodic task.
    """
    try:
        from .jira_client import check_jira_connection
        from .notion_client import check_notion_connection

        next_run = {}
        if scheduler and scheduler.get_jobs():
            for job in scheduler.get_jobs():
                next_run[job.id] = job.next_run_time.isoformat()

        last_keys = {p.key: state.get_last_key(p.key) for p in settings.projects}
        notion_db = settings.projects[0].database_id if settings.projects else None

        return {
            "status": "running",
            "last_processed_issue": last_keys,
            "jira_connected": await check_jira_connection(),
            "notion_connected": await check_notion_connection(notion_db),
            "next_run": next_run,
        }
    except Exception as e:
        logger.error(f"Error in /status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error checking service status: {str(e)}"
        )


@app.on_event("startup")
async def startup_event():
    """Initial configuration when starting the application"""
    global scheduler

    scheduler = AsyncIOScheduler()

    for project in settings.projects:
        scheduler.add_job(
            periodic_task,
            trigger="interval",
            seconds=settings.check_interval,
            args=[project, state.get_last_key(project.key)],
            id=f"periodic_task_{project.key}",
            max_instances=1,
            replace_existing=True,
        )
    scheduler.start()

    logger.info("Service started successfully")
    logger.info(f"Check interval: {settings.check_interval} seconds")
    for project in settings.projects:
        logger.info(
            f"Last processed issue for {project.key}: {state.get_last_key(project.key)}"
        )


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
    Synchronize all tickets assigned to the configured Jira user
    with the Notion database:
    - Create new pages if they do not exist.
    - Update status to 'Initial' if they already exist.
    """
    if not settings.projects:
        raise HTTPException(status_code=400, detail="No projects configured")
    return await sync_all_user_issues(settings.projects[0].database_id)

