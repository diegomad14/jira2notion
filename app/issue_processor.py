# issue_processor.py
import asyncio  # 👈 Agregar esta línea
from .jira_client import get_new_issues, get_updated_issues
from .notion_client import create_or_update_notion_page, create_notion_page, update_notion_page
from .filters import filter_issues_by_assignee
from .logger_config import setup_logger
from .config import settings
from .notion_client import find_notion_page_by_ticket, set_notion_verificado
from fastapi import HTTPException


logger = setup_logger()

async def process_updated_issues(last_key):
    """
    Procesa los issues actualizados desde el último issue registrado.
    """
    issues = await get_updated_issues()  # Obtiene los issues actualizados

    if not issues:
        logger.info("No hay nuevos issues ni actualizaciones.")
        return {"message": "No new updates."}
    
    last_processed_issue = None  # Guardará el último issue procesado

    for issue in issues:
        issue_key = issue.key  # Accede al atributo 'key' del objeto JiraIssue
        logger.info(f"Procesando issue actualizado: {issue_key}")

        # Verificar si ya existe la página en Notion
        existing_page = await create_or_update_notion_page(issue_key)

        if not existing_page:
            logger.info(f"No se encontró página existente para el issue {issue_key}, creando una nueva...")
            await create_notion_page(issue)
        else:
            logger.info(f"La página ya existe para el issue {issue_key}, se actualizará si es necesario.")
            await update_notion_page(issue, existing_page)

        last_processed_issue = issue_key  # Actualizar el último issue procesado

    if last_processed_issue:
        # Actualiza el estado con el último issue procesado
        await state.update_last_key(last_processed_issue)  # Asegúrate de que esta línea se ejecute correctamente
    
    return {"message": "Processed all updated issues.", "last_issue": last_processed_issue}

async def process_new_issues(last_processed_issue_key):
    try:
        logger.info("Iniciando verificación de nuevos issues en Jira")
        issues = await get_new_issues()
        
        if issues:
            logger.info(f"Se obtuvieron {len(issues)} issues nuevos desde Jira")
            filtered_issues = filter_issues_by_assignee(issues, settings.jira_assignee)
            
            if filtered_issues:
                latest_issue = filtered_issues[0]
                if latest_issue.key != last_processed_issue_key:
                    logger.info(f"Nuevo issue detectado: {latest_issue.key}")
                    
                    # Se crea o actualiza la página en Notion según corresponda
                    await create_or_update_notion_page(latest_issue)
                    last_processed_issue_key = latest_issue.key
                    
                    logger.info(f"Página de Notion creada o actualizada para el issue: {latest_issue.key}")
                    return {"message": "Nuevo issue procesado", "issue_key": latest_issue.key}
                else:
                    logger.info(f"No hay nuevos issues asignados a {settings.jira_assignee}")
                    return {"message": "No hay nuevos issues"}
            else:
                logger.info(f"No hay issues asignados a {settings.jira_assignee} en esta actualización")
                return {"message": f"No hay issues asignados a {settings.jira_assignee} en esta actualización"}
        else:
            logger.info("No se encontraron issues nuevos en Jira")
            return {"message": "No hay nuevos issues"}
    except Exception as e:
        logger.error(f"Error en el procesamiento de nuevos issues: {e}")
        raise

async def periodic_task(last_processed_issue_key):
    while True:
        try:
            issues = await get_updated_issues()
            logger.info(f"Se obtuvieron {len(issues)} issues actualizados")
            filtered_issues = filter_issues_by_assignee(issues, settings.jira_assignee)
            
            if filtered_issues:
                latest_issue = filtered_issues[0]
                if latest_issue.key != last_processed_issue_key:
                    logger.info(f"Nuevo issue o actualización detectado: {latest_issue.key}")

                    # Se crea o actualiza la página en Notion (evitando duplicidad)
                    await create_or_update_notion_page(latest_issue)
                    last_processed_issue_key = latest_issue.key
                else:
                    logger.info("No hay nuevos issues ni actualizaciones.")
            else:
                logger.info(f"No hay issues asignados a {settings.jira_assignee}.")
        except Exception as e:
            logger.error(f"Error en la tarea periódica: {e}")
        await asyncio.sleep(settings.check_interval)

async def sync_all_user_issues():
    try:
        logger.info("Iniciando sincronización completa de issues asignados al usuario")

        # 1. Obtener todos los issues asignados al usuario con estados deseados
        jql = (
            'assignee = currentUser() AND '
            'status IN ("To Do","In Progress","Impact Estimated","QUARANTINE",'
            '"Resolution In Progress","Routing","Waiting For Customer") '
            'ORDER BY updated DESC'
        )
        from .jira_client import _fetch_issues
        issues = await _fetch_issues(jql)

        if not issues:
            return {"message": "No hay issues asignados a este usuario."}

        processed_issues = []

        for issue in issues:
            issue_key = issue.key
            logger.info(f"Sincronizando issue: {issue_key}")

            # Verificar si ya existe en Notion
            existing_page = await find_notion_page_by_ticket(issue_key)

            if existing_page:
                logger.info(f"Actualizando estado a 'Inicial' para la página existente de {issue_key}")
                await set_notion_verificado(existing_page, False)
                await update_notion_page(existing_page["id"], issue)
            else:
                logger.info(f"Creando nueva página en Notion con estado 'Inicial' para {issue_key}")
                await create_notion_page(issue)

            processed_issues.append(issue_key)

        return {"message": f"Sincronizados {len(processed_issues)} issues", "issues": processed_issues}

    except Exception as e:
        logger.error(f"Error en sincronización completa: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
