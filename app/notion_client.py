import os
import logging
import json
import ast
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pytz
import yaml
from notion_client import AsyncClient
from typing import Optional

from .models import JiraIssue

logger = logging.getLogger(__name__)

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
JIRA_DOMAIN = os.getenv("JIRA_DOMAIN")

# Load Jira field to Notion property mapping
FIELD_MAP_PATH = Path(__file__).with_name("field_map.yaml")
with FIELD_MAP_PATH.open("r", encoding="utf-8") as f:
    FIELD_MAP: dict[str, str] = yaml.safe_load(f) or {}

notion = AsyncClient(auth=NOTION_API_KEY)

# Cache for Notion database property names
_NOTION_PROPERTIES: Optional[set[str]] = None


async def get_database_properties() -> set[str]:
    """Return the set of property names defined in the target Notion database."""
    global _NOTION_PROPERTIES
    if _NOTION_PROPERTIES is None:
        try:
            response = await notion.databases.retrieve(NOTION_DATABASE_ID)
            _NOTION_PROPERTIES = set(response.get("properties", {}).keys())
        except Exception as e:
            logger.error(f"Error retrieving Notion database properties: {e}")
            _NOTION_PROPERTIES = set()
    return _NOTION_PROPERTIES

async def check_notion_connection() -> bool:
    """
    Verify the connection with the Notion API.
    Returns True if the connection is successful, False otherwise.
    """
    try:
        client = AsyncClient(auth=NOTION_API_KEY)

        response = await client.databases.retrieve(NOTION_DATABASE_ID)

        if response:
            return True
        return False
    except Exception as e:
        logging.error(f"Error connecting to Notion: {e}")
        return False



def parse_jira_description(description):
    """Parse the Jira ticket description into formatted text."""
    if not description:
        return ""

    description_json = None
    if isinstance(description, dict):
        description_json = description
    else:
        try:
            description_json = json.loads(description)
        except json.JSONDecodeError:
            try:
                description_json = ast.literal_eval(description)
            except (ValueError, SyntaxError) as e:
                logger.error(f"Error parsing Jira description: {e}")
                return description
        except Exception as e:
            logger.error(f"Error parsing Jira description: {e}")
            return description

    try:
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


async def build_properties(
    mapping: dict[str, str], issue: JiraIssue, existing_props: Optional[set[str]] = None
) -> dict[str, dict]:
    """Build a Notion properties payload from a Jira issue using the field mapping."""
    if existing_props is None:
        existing_props = await get_database_properties()

    # Parse creation date once for reuse
    created_str = issue.get("created", "")
    if "T" in created_str:
        created_date = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%S.%f%z")
    else:
        created_date = datetime.strptime(created_str, "%Y-%m-%d")
    colombia_tz = timezone(timedelta(hours=-5))
    created_date = created_date.replace(tzinfo=colombia_tz)
    created_date_iso = created_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    properties: dict[str, dict] = {}
    for jira_field, notion_prop in mapping.items():
        if notion_prop not in existing_props:
            logger.warning(
                f"Skipping unknown Notion property '{notion_prop}' while building properties"
            )
            continue
        value = issue.get(jira_field)
        if value is None:
            if jira_field == "customfield_12286":
                value = issue.get("description_rest")
            elif jira_field == "description":
                value = issue.get("description_adv")
        if jira_field == "summary":
            properties[notion_prop] = {
                "title": [{"type": "text", "text": {"content": value or ""}}]
            }
        elif jira_field == "key":
            properties[notion_prop] = {
                "rich_text": [{"type": "text", "text": {"content": value or ""}}]
            }
        elif jira_field == "created":
            properties[notion_prop] = {"date": {"start": created_date_iso}}
        elif jira_field in ("reporter", "assignee"):
            name = value.get("displayName", "Unknown") if value else "Unknown"
            properties[notion_prop] = {
                "rich_text": [{"type": "text", "text": {"content": name}}]
            }
        elif jira_field in ("description", "customfield_12286"):
            parsed = parse_jira_description(value) if value else ""
            properties[notion_prop] = {
                "rich_text": [{"type": "text", "text": {"content": parsed}}]
            }
        else:
            properties[notion_prop] = {
                "rich_text": [{"type": "text", "text": {"content": str(value) if value is not None else ""}}]
            }

    return properties


async def find_notion_page_by_ticket(ticket_key: str) -> dict:
    """
    Query Notion to find a page whose Jira key field matches the ticket_key.
    """
    try:
        key_property = FIELD_MAP.get("key", "Jira Issue Key")
        query = {
            "filter": {
                "property": key_property,
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
        logger.error(f"Error searching Notion page for ticket {ticket_key}: {e}")
    return None


async def create_notion_page(issue: JiraIssue):
    """Create a new page in Notion using the issue information."""
    try:
        logger.info(f"Creating Notion page for issue: {issue.get('key')}")
        key_content = issue.get("key") or ""
        description_rest_content = parse_jira_description(issue.get("description_rest")) if issue.get("description_rest") else ""
        description_adv_content = parse_jira_description(issue.get("description_adv")) if issue.get("description_adv") else ""
        markdown_content = [
            {
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Critical Points for Ticket Management"}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "toggle",
                "toggle": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Ticket Closure"}}
                    ],
                    "children": [
                        {
                            "object": "block",
                            "type": "to_do",
                            "to_do": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": "Categorization and Tags: Ensure the correct categorization and tags are included on all closed tickets."}
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
                                        "text": {"content": "Correct Ticket Type: Verify that tickets from other Issue Types are not closed as *Issue Type Rest*."}
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
                                        "text": {"content": "Linked Ticket: Ensure each *Production Bug* has a linked ticket."}
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
                                        "text": {"content": "Duplicates: Escalated duplicates should remain as *Production Bug* and be completed."}
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
                                        "text": {"content": "No Component: Do not assign components to closed duplicates."}
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
                                        "text": {"content": "Consistency: Ensure the main issue and the duplicate are categorized correctly."}
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
                        {"type": "text", "text": {"content": "Escalations"}}
                    ],
                    "children": [
                        {
                            "object": "block",
                            "type": "to_do",
                            "to_do": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {"content": "Assignee: Ensure it is always the corresponding EL for each team."}
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
                                        "text": {"content": "Required Components and Data: Confirm that all necessary data and components are included."}
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
                                        "text": {"content": "ETA IM: Ensure each case has the RSUP or ADVS ETA IM before being in *Escalated* status."}
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
                                        "text": {"content": "Escalation Fields: Complete all required fields."}
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
                                        "text": {"content": "Complete Documentation: Record the corresponding PM, provide detailed case evidence in the description, and ensure cases handled by the NOC are documented by whoever handled them."}
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
                        {"type": "text", "text": {"content": "Notes"}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Make sure the entire backlog is up to date before **01/31**."}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Verify that tickets created in 2025 are properly categorized."}}
                    ]
                }
            }
        ]
        rest_chunks = split_text("Rest Description:\n" + description_rest_content)
        adv_chunks = split_text("Revenue Description:\n" + description_adv_content)
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

        existing_props = await get_database_properties()
        properties = await build_properties(FIELD_MAP, issue, existing_props)

        # Add static properties if they exist in the database
        static_props = {
            "Tags": {"multi_select": [{"name": "trabajo"}]},
            "Asignación": {"people": [{"id": "564716e3-359a-48a0-b3ea-e54c74902573"}]},
            "Verificado": {"checkbox": False},
        }
        for prop_name, prop_value in static_props.items():
            if prop_name in existing_props:
                properties[prop_name] = prop_value
            else:
                logger.warning(
                    f"Skipping static Notion property '{prop_name}' while creating page"
                )

        payload = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": properties,
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
                                    "link": {"url": f"{JIRA_DOMAIN}/browse/{key_content}"}
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
                                    "content": "Action Items"
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
        logger.info(f"Page successfully created in Notion for issue: {issue.get('key')}")
        return response
    except Exception as e:
        logger.error(f"Error creating Notion page for issue {issue.get('key')}: {e}")
        raise


async def update_notion_page(page_id: str, issue: JiraIssue):
    """Update the existing Notion page with the current issue information."""
    try:
        issue_key = issue.get("key", "UNKNOWN")
        logger.info(f"Updating Notion page for issue: {issue_key}")

        existing_props = await get_database_properties()


        properties = await build_properties(FIELD_MAP, issue, existing_props)


        static_props = {
            "Tags": {"multi_select": [{"name": "trabajo"}]},
            "Asignación": {"people": [{"id": "564716e3-359a-48a0-b3ea-e54c74902573"}]},
        }
        for prop_name, prop_value in static_props.items():
            if prop_name in existing_props:
                properties[prop_name] = prop_value
            else:
                logger.warning(
                    f"Skipping static Notion property '{prop_name}' while updating page"
                )

        payload = {"properties": properties}

        response = await notion.pages.update(page_id=page_id, **payload)
        logger.info(f"Page successfully updated in Notion for issue: {issue_key}")
        return response

    except Exception as e:
        issue_key = issue.get("key", "UNKNOWN")
        logger.error(f"Error updating Notion page for issue {issue_key}: {e}")
        raise

async def create_or_update_notion_page(issue: JiraIssue):
    """
    Function that first checks if a Notion page already exists for the issue.
    If it exists, it is updated; otherwise, a new one is created.
    """
    try:
        existing_page = await find_notion_page_by_ticket(issue.get("key"))
        if existing_page:
            page_id = existing_page.get("id")
            logger.info(f"Page already exists for issue {issue.get('key')}, proceeding to update.")
            return await update_notion_page(page_id, issue)
        else:
            logger.info(f"No existing page found for issue {issue.get('key')}, creating a new one.")
            return await create_notion_page(issue)
    except Exception as e:
        logger.error(f"Error in create_or_update_notion_page for issue {issue.get('key')}: {e}")
        raise

async def set_notion_verified(page: dict, verified) -> dict:
    """
    Update the checkbox field 'Verificado' on the Notion page.
    The value can be a boolean or a convertible string (like "True", "Initial", etc.).
    """
    try:
        existing_props = await get_database_properties()
        if "Verificado" not in existing_props:
            logger.warning("Property 'Verificado' not found in Notion database; skipping update")
            return page

        if isinstance(verified, str):
            verified_bool = verified.strip().lower() == "true"
        else:
            verified_bool = bool(verified)

        page_id = page["id"]
        payload = {
            "properties": {
                "Verificado": {
                    "checkbox": verified_bool
                }
            }
        }
        response = await notion.pages.update(page_id=page_id, **payload)
        logger.info(f"Field 'Verificado' updated to {verified_bool} on page {page_id}")
        return response
    except Exception as e:
        logger.error(
            f"Error updating 'Verificado' field in Notion for page {page.get('id', 'unknown')}: {e}"
        )
        raise


def split_text(text: str, chunk_size: int = 2000) -> list[str]:
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
