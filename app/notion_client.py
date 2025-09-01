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
    """
    Parse the Jira ticket description into formatted text.
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
    Query Notion for a page whose "Jira Issue Key" matches the given ticket_key.
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
        logger.error(f"Error searching for page in Notion for ticket {ticket_key}: {e}")
    return None


async def create_notion_page(issue: JiraIssue):
    """
    Create a new page in Notion using the issue information.
    """
    try:
        logger.info(f"Creating page in Notion for issue: {issue.key}")
        reporter_name = issue.reporter.get("displayName", "Unknown") if issue.reporter else "Unknown"
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
                                        "text": {"content": "Categorization and Tags: Ensure that categorization and appropriate tags are included in all closed tickets."}
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
                                        "text": {"content": "Correct Ticket Type: Verify that tickets of other Issue Types are not closed as *Issue Type Rest*."}
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
                                        "text": {"content": "Linked Ticket: Confirm that every *Production Bug* has a linked ticket."}
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
                                        "text": {"content": "Duplicates: Escalation duplicates must remain as *Production Bug* and be closed."}
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
                                        "text": {"content": "Consistency: Ensure that the main ticket and the duplicate are properly categorized."}
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
                                        "text": {"content": "Assignee: Ensure it is always the corresponding EL of each team."}
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
                                        "text": {"content": "Components and Required Data: Confirm that all necessary data and components are included."}
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
                                        "text": {"content": "ETA IM: Ensure each case has the RSUP or ADVS ETA IM before being in *Escalated* state."}
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
                                        "text": {"content": "Complete Documentation: Record the corresponding PM, leave detailed case evidence in the description, and ensure that cases handled by the NOC are documented by the person who worked on them."}
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
                        {"type": "text", "text": {"content": "Ensure the entire backlog is up to date before **01/31**."}}
                    ]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Verify that tickets created in 2025 are correctly categorized."}}
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
                "Creation Date": {
                    "date": {"start": created_date_iso}
                },
                "Tags": {
                    "multi_select": [{"name": "work"}]
                },
                "Assignment": {
                    "people": [{"id": "564716e3-359a-48a0-b3ea-e54c74902573"}]
                },
                "Verified": {
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
        logger.info(f"Page successfully created in Notion for issue: {issue.key}")
        return response
    except Exception as e:
        logger.error(f"Error creating page in Notion for issue {issue.key}: {e}")
        raise


async def update_notion_page(page_id: str, issue: JiraIssue):
    """
    Update the existing Notion page with the current issue information.
    """
    try:
        issue_key = getattr(issue, "key", "UNKNOWN")
        logger.info(f"Updating Notion page for issue: {issue_key}")

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
        logger.info(f"Page successfully updated in Notion for issue: {issue_key}")
        return response

    except Exception as e:
        issue_key = getattr(issue, "key", "UNKNOWN")
        logger.error(f"Error updating the page in Notion for issue {issue_key}: {e}")
        raise

async def create_or_update_notion_page(issue: JiraIssue):
    """
    Function that first checks if a Notion page already exists for the issue.
    If it exists, it is updated; otherwise, a new one is created.
    """
    try:
        existing_page = await find_notion_page_by_ticket(issue.key)
        if existing_page:
            page_id = existing_page.get("id")
            logger.info(f"Page already exists for issue {issue.key}, proceeding to update.")
            return await update_notion_page(page_id, issue)
        else:
            logger.info(f"No existing page found for issue {issue.key}, creating a new one.")
            return await create_notion_page(issue)
    except Exception as e:
        logger.error(f"Error in create_or_update_notion_page for issue {issue.key}: {e}")
        raise

async def set_notion_verified(page: dict, verified) -> dict:
    """
    Update the checkbox field 'Verified' of the page in Notion.
    The value can be a boolean or a convertible string (such as "True", "Initial", etc.).
    """
    try:
        if isinstance(verified, str):
            verified_bool = verified.strip().lower() == "true"
        else:
            verified_bool = bool(verified)

        page_id = page["id"]
        payload = {
            "properties": {
                "Verified": {
                    "checkbox": verified_bool
                }
            }
        }
        response = await notion.pages.update(page_id=page_id, **payload)
        logger.info(f"Field 'Verified' updated to {verified_bool} on page {page_id}")
        return response
    except Exception as e:
        logger.error(f"Error updating 'Verified' field in Notion for page {page.get('id', 'unknown')}: {e}")
        raise


def split_text(text: str, chunk_size: int = 2000) -> list[str]:
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
