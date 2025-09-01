# main.py
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

# Configuración inicial de FastAPI
app = FastAPI(
    title="Jira2Notion Sync API",
    description="API para sincronización de tickets entre Jira y Notion",
    version="1.0.0"
)

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicialización de componentes
logger = setup_logger()
state = StateManager()

scheduler: AsyncIOScheduler = None  # Scheduler global


@app.get("/")
async def read_root() -> Dict[str, str]:
    """Endpoint básico para verificar el estado del servicio"""
    return {"message": "Jira2Notion integration is running!"}


@app.post("/check-updated-issues")
async def check_updated_issues() -> JSONResponse:
    """
    Endpoint para verificar y procesar issues actualizados en Jira.
    Se utiliza la función que ya realiza la verificación de duplicados mediante
    la lógica de 'create_or_update_notion_page'.
    """
    try:
        last_key = state.get_last_key()
        logger.info(f"Último issue procesado: {last_key}")

        result = await process_updated_issues(last_key)

        if "issue_key" in result:
            state.update_last_key(result["issue_key"])
            logger.info(f"Nuevo último issue procesado: {result['issue_key']}")

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Error en /check-updated-issues: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        )


@app.post("/check-new-issues")
async def check_new_issues() -> JSONResponse:
    """
    Endpoint para verificar y procesar nuevos issues en Jira.
    Se utiliza la función que, a través de 'create_or_update_notion_page',
    evita crear páginas duplicadas en Notion.
    """
    try:
        last_key = state.get_last_key()
        logger.info(f"Último issue procesado: {last_key}")

        result = await process_new_issues(last_key)

        if "issue_key" in result:
            state.update_last_key(result["issue_key"])
            logger.info(f"Nuevo último issue procesado: {result['issue_key']}")

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Error en /check-new-issues: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        )


@app.get("/status")
async def service_status() -> Dict[str, Any]:
    """
    Endpoint de estado del servicio.
    Reporta la conexión con Jira y Notion, el último issue procesado y
    el próximo tiempo de ejecución de la tarea periódica.
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
        logger.error(f"Error en /status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error checking service status: {str(e)}"
        )


@app.on_event("startup")
async def startup_event():
    """Configuración inicial al iniciar la aplicación"""
    global scheduler

    scheduler = AsyncIOScheduler()

    # Se programa la tarea periódica. Se pasa el último issue procesado,
    # y se configura para que no existan ejecuciones simultáneas (max_instances=1)
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

    logger.info("Servicio iniciado correctamente")
    logger.info(f"Intervalo de verificación: {settings.check_interval} segundos")
    logger.info(f"Último issue procesado: {state.get_last_key()}")


@app.on_event("shutdown")
async def shutdown_event():
    """Manejo del cierre de la aplicación"""
    global scheduler
    if scheduler:
        scheduler.shutdown()
    logger.info("Servicio detenido correctamente")

from .issue_processor import sync_all_user_issues

@app.post("/sync-user-issues")
async def sync_user_issues():
    """
    Sincroniza todos los tickets asignados al usuario configurado en Jira,
    con la base de datos de Notion:
    - Crea nuevas páginas si no existen.
    - Actualiza estado a 'Inicial' si ya existen.
    """
    return await sync_all_user_issues()

