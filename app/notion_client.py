import os
import logging
from notion_client import AsyncClient
from .models import JiraIssue
from datetime import datetime, timezone, timedelta
import pytz

logger = logging.getLogger(__name__)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

notion = AsyncClient(auth=NOTION_API_KEY)

async def check_notion_connection() -> bool:
    """
    Verifica la conexión con la API de Notion.
    Retorna True si la conexión es exitosa, False si falla.
    """
    try:
        client = AsyncClient(auth=NOTION_API_KEY)

        response = await client.databases.retrieve(NOTION_DATABASE_ID)

        if response:
            return True
        return False
    except Exception as e:
        logging.error(f"Error en la conexión con Notion: {e}")
        return False



def parse_jira_description(description):
    """
    Parsea la descripción del ticket de Jira para convertirla en un texto formateado.
    """
    if not description:
        return ""
    
    try:
        description_json = description if isinstance(description, dict) else eval(description)
        content = description_json.get('content', [])
        formatted_text = ""

        for block in content:
            if block.get('type') == 'bulletList':
                for item in block.get('content', []):
                    if item.get('type') == 'listItem':
                        for paragraph in item.get('content', []):
                            if paragraph.get('type') == 'paragraph':
                                for text_block in paragraph.get('content', []):
                                    if text_block.get('type') == 'text':
                                        formatted_text += "* " + text_block.get('text', '') + "\n"
            elif block.get('type') == 'paragraph':
                for text_block in block.get('content', []):
                    if text_block.get('type') == 'text':
                        formatted_text += text_block.get('text', '') + "\n"
                    elif text_block.get('type') == 'hardBreak':
                        formatted_text += "\n"

        return formatted_text.strip()
    except Exception as e:
        logger.error(f"Error parsing Jira description: {e}")
        return description


async def find_notion_page_by_ticket(ticket_key: str) -> dict:
    """
    Consulta Notion para buscar una página cuyo campo "Jira Issue Key" coincida con el ticket_key.
    """
    try:
        query = {
            "filter": {
                "property": "Jira Issue Key",
                "rich_text": {
                    "equals": ticket_key
                }
            }
        }
        response = await notion.databases.query(database_id=NOTION_DATABASE_ID, **query)
        results = response.get("results", [])
        if results:
            return results[0]
    except Exception as e:
        logger.error(f"Error buscando página en Notion para ticket {ticket_key}: {e}")
    return None


async def create_notion_page(issue: JiraIssue):
    """
    Crea una nueva página en Notion usando la información del issue.
    """
    try:
        logger.info(f"Creando página en Notion para el issue: {issue.key}")
        reporter_name = issue.reporter.get("displayName", "Desconocido") if issue.reporter else "Desconocido"
        key_content = issue.key if issue.key else ""
        description_rest_content = parse_jira_description(issue.description_rest) if issue.description_rest else ""
        description_adv_content = parse_jira_description(issue.description_adv) if issue.description_adv else ""
        if "T" in issue.created:
            created_date = datetime.strptime(issue.created, "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            created_date = datetime.strptime(issue.created, "%Y-%m-%d")
        colombia_tz = timezone(timedelta(hours=-5))
        created_date = created_date.replace(tzinfo=colombia_tz)
        created_date_utc = created_date.astimezone(timezone.utc)
        created_date_iso = created_date_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        markdown_content = [
            {
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Puntos Críticos para Gestión de Tickets"}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "toggle",
                "toggle": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Cierre de Tickets"}}
                    ],
                    "children": [
                        {
                            "object": "block",
                            "type": "to_do",
                            "to_do": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": "Tipificación y Etiquetas: Asegurarse de incluir la tipificación y las etiquetas adecuadas en todos los tickets cerrados."}
                                    }
                                ],
                                "checked": False
                            }
                        }
                    ]
                }
            },
            {
                "object": "block",
                "type": "toggle",
                "toggle": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "General"}}
                    ],
                    "children": [
                        {
                            "object": "block",
                            "type": "to_do",
                            "to_do": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": "Tipo de Ticket Correcto: Verificar que los tickets de otros Issue Types no sean cerrados como *Issue Type Rest*."}
                                    }
                                ],
                                "checked": False
                            }
                        }
                    ]
                }
            },
            {
                "object": "block",
                "type": "toggle",
                "toggle": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Production Bug"}}
                    ],
                    "children": [
                        {
                            "object": "block",
                            "type": "to_do",
                            "to_do": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": "Ticket Linkeado: Confirmar que cada *Production Bug* tenga un ticket vinculado."}
                                    }
                                ],
                                "checked": False
                            }
                        },
                        {
                            "object": "block",
                            "type": "to_do",
                            "to_do": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": "Duplicados: Duplicados de escalados deben quedar como *Production Bug* y finalizados."}
                                    }
                                ],
                                "checked": False
                            }
                        },
                        {
                            "object": "block",
                            "type": "to_do",
                            "to_do": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": "Sin componente: No asignar componentes a duplicados cerrados."}
                                    }
                                ],
                                "checked": False
                            }
                        },
                        {
                            "object": "block",
                            "type": "to_do",
                            "to_do": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": "Consistencia: Asegurar que el principal y el duplicado queden correctamente tipificados."}
                                    }
                                ],
                                "checked": False
                            }
                        }
                    ]
                }
            },
            {
                "object": "block",
                "type": "toggle",
                "toggle": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Escalados"}}
                    ],
                    "children": [
                        {
                            "object": "block",
                            "type": "to_do",
                            "to_do": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": "Assignee: Asegurar que siempre sea el EL correspondiente de cada equipo."}
                                    }
                                ],
                                "checked": False
                            }
                        },
                        {
                            "object": "block",
                            "type": "to_do",
                            "to_do": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": "Componentes y Datos Obligatorios: Confirmar que se incluyan todos los datos y componentes necesarios."}
                                    }
                                ],
                                "checked": False
                            }
                        },
                        {
                            "object": "block",
                            "type": "to_do",
                            "to_do": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": "ETA IM: Asegurarse de que cada caso tenga el ETA IM del RSUP o ADVS antes de estar en estado *Escalated*."}
                                    }
                                ],
                                "checked": False
                            }
                        },
                        {
                            "object": "block",
                            "type": "to_do",
                            "to_do": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": "Campos de Escalado: Completar todos los campos obligatorios."}
                                    }
                                ],
                                "checked": False
                            }
                        },
                        {
                            "object": "block",
                            "type": "to_do",
                            "to_do": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": "Documentación Completa: Registrar el PM correspondiente, dejar evidencia detallada del caso en la descripción, y asegurar que los casos gestionados por el NOC sean documentados por quien los llevó."}
                                    }
                                ],
                                "checked": False
                            }
                        }
                    ]
                }
            },
            {
                "object": "block",
                "type": "divider",
                "divider": {}
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Notas"}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Revisar que todo el backlog esté al día antes del **31/01**."}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Verificar que los tickets creados en 2025 estén correctamente tipificados."}}
                    ]
                }
            }
        ]
        rest_chunks = split_text("Descripción Rest:\n" + description_rest_content)
        adv_chunks = split_text("Descripción Revenue:\n" + description_adv_content)
        rest_blocks = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                }
            }
            for chunk in rest_chunks
        ]

        adv_blocks = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                }
            }
            for chunk in adv_chunks
        ]

        payload = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": {
                "Name": {
                    "title": [{"type": "text", "text": {"content": issue.summary}}]
                },
                "Jira Issue Key": {
                    "rich_text": [{"type": "text", "text": {"content": issue.key}}]
                },
                "Reporter": {
                    "rich_text": [{"type": "text", "text": {"content": reporter_name}}]
                },
                "Fecha de creación": {
                    "date": {"start": created_date_iso}
                },
                "Tags": {
                    "multi_select": [{"name": "trabajo"}]
                },
                "Asignación": {
                    "people": [{"id": "564716e3-359a-48a0-b3ea-e54c74902573"}]
                },
                "Verificado": {
                    "checkbox": False
                }
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": "Issue URL: "
                                }
                            },
                            {
                                "type": "text",
                                "text": {
                                    "content": key_content,
                                    "link": {"url": f"https://example.atlassian.net/browse/{key_content}"}
                                }
                            }
                        ]
                    }
                },
                {
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": "Accionables"
                                },
                                "annotations": {
                                    "bold": True,
                                    "italic": False,
                                    "underline": False,
                                    "color": "yellow"
                                }
                            }
                        ],
                        "icon": {
                            "type": "emoji",
                            "emoji": "📝"
                        },
                        "children": [
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [
                                        {
                                            "type": "text",
                                            "text": {
                                                "content": " "
                                            },
                                            "annotations": {
                                                "bold": False,
                                                "italic": False,
                                                "underline": False,
                                                "color": "default"
                                            }
                                        }
                                    ]
                                }
                            },
                        ]
                    }
                },
                *rest_blocks,
                *adv_blocks,
                *markdown_content
            ]
        }

        response = await notion.pages.create(**payload)
        logger.info(f"Página creada exitosamente en Notion para el issue: {issue.key}")
        return response
    except Exception as e:
        logger.error(f"Error al crear la página en Notion para el issue {issue.key}: {e}")
        raise


async def update_notion_page(page_id: str, issue: JiraIssue):
    """
    Actualiza la página existente en Notion con la información actual del issue.
    """
    try:
        issue_key = getattr(issue, "key", "UNKNOWN")
        logger.info(f"Actualizando página en Notion para el issue: {issue_key}")

        summary = getattr(issue, "summary", "")
        description_content = parse_jira_description(getattr(issue, "description", "")) or ""
        customfield_content = getattr(issue, "customfield_12286", "") or ""

        payload = {
            "properties": {
                "Name": {
                    "title": [{"type": "text", "text": {"content": summary}}]
                },
                "Jira Issue Key": {
                    "rich_text": [{"type": "text", "text": {"content": issue_key}}]
                }
            }
        }

        response = await notion.pages.update(page_id=page_id, **payload)
        logger.info(f"Página actualizada exitosamente en Notion para el issue: {issue_key}")
        return response

    except Exception as e:
        issue_key = getattr(issue, "key", "UNKNOWN")
        logger.error(f"Error al actualizar la página en Notion para el issue {issue_key}: {e}")
        raise

async def create_or_update_notion_page(issue: JiraIssue):
    """
    Función que primero busca si ya existe una página en Notion para el issue.
    Si existe, se actualiza; de lo contrario, se crea una nueva.
    """
    try:
        existing_page = await find_notion_page_by_ticket(issue.key)
        if existing_page:
            page_id = existing_page.get("id")
            logger.info(f"Página ya existe para el issue {issue.key}, se procederá a actualizarla.")
            return await update_notion_page(page_id, issue)
        else:
            logger.info(f"No se encontró página existente para el issue {issue.key}, se creará una nueva.")
            return await create_notion_page(issue)
    except Exception as e:
        logger.error(f"Error en create_or_update_notion_page para el issue {issue.key}: {e}")
        raise

async def set_notion_verificado(page: dict, verificado) -> dict:
    """
    Actualiza el campo tipo checkbox 'Verificado' de la página en Notion.
    El valor puede ser booleano o un string convertible (como "True", "Inicial", etc.).
    """
    try:
        if isinstance(verificado, str):
            verificado_bool = verificado.strip().lower() == "true"
        else:
            verificado_bool = bool(verificado)

        page_id = page["id"]
        payload = {
            "properties": {
                "Verificado": {
                    "checkbox": verificado_bool
                }
            }
        }
        response = await notion.pages.update(page_id=page_id, **payload)
        logger.info(f"Campo 'Verificado' actualizado a {verificado_bool} en página {page_id}")
        return response
    except Exception as e:
        logger.error(f"Error al actualizar campo 'Verificado' en Notion para la página {page.get('id', 'desconocida')}: {e}")
        raise


def split_text(text: str, chunk_size: int = 2000) -> list[str]:
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
