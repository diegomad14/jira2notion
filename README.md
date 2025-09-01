# Jira2Notion

**Jira2Notion** is a real-time synchronization service between
**Atlassian Jira** and **Notion**, designed to keep project visibility
consistent across both platforms.\
The system monitors Jira issues and creates/updates corresponding pages
in a Notion database, eliminating the need for manual synchronization.

------------------------------------------------------------------------

## ✨ Features

-   🔄 **Automated Synchronization**: continuously monitors Jira issues
    with configurable intervals.\
-   ⚡ **Manual Triggers**: REST API endpoints for on-demand
    synchronization.\
-   🧠 **Smart Updates**: prevents duplicates and selectively updates
    based on issue changes.\
-   👤 **User Filtering**: sync only issues assigned to a specific
    user.\
-   💾 **Persistent State Management**: ensures reliable resumption
    after restarts using TinyDB.\
-   📑 **Structured Logging**: rotating logs stored in file and console
    for monitoring and debugging.

### 🗂️ Multiple Project Synchronization

-   Set the `PROJECTS` environment variable to a JSON array where each
    entry contains the Jira key, a project-specific JQL filter, and
    optionally a Notion database ID.
-   The `get_new_issues` and `get_updated_issues` functions combine the
    time window with the project's filter to build the final JQL query.
-   The entry point iterates over this list and synchronizes each
    project independently, tracking the last processed issue for each
    one.

------------------------------------------------------------------------

## 🏗️ System Architecture

-   **FastAPI Web Server**: exposes REST endpoints and manages the
    application lifecycle.\
-   **Issue Processor**: core synchronization logic between Jira and
    Notion.\
-   **Jira Client**: integration with Jira REST API (issues &
    changelogs).\
-   **Notion Client**: integration with Notion API for page management.\
-   **State Manager**: persistence of the last processed issue
    (TinyDB).\
-   **Scheduler (APScheduler)**: executes periodic background sync
    tasks.\
-   **Infrastructure Support**: environment-based configuration,
    logging, and assignee filters.

------------------------------------------------------------------------

## 📦 Main Dependencies

-   [FastAPI](https://fastapi.tiangolo.com/) --- ASGI web framework.\
-   [Uvicorn](https://www.uvicorn.org/) --- ASGI server for FastAPI.\
-   [APScheduler](https://apscheduler.readthedocs.io/) --- job
    scheduling.\
-   [Pydantic](https://docs.pydantic.dev/) --- data validation &
    settings.\
-   [TinyDB](https://tinydb.readthedocs.io/) --- lightweight JSON
    persistence.\
-   [Requests](https://docs.python-requests.org/) --- Jira API
    communication.\
-   [httpx](https://www.python-httpx.org/) --- async HTTP client (used
    by notion-client).\
-   [notion-client](https://github.com/ramnes/notion-sdk-py) ---
    official Notion API client.

------------------------------------------------------------------------

## ⚙️ Configuration

The system relies on environment variables (via `.env` or system
environment):

  ----------------------------------------------------------------------------------
  Variable               Description                      Example
  ---------------------- -------------------------------- --------------------------
  `JIRA_EMAIL`           Jira account email               `user@company.com`

  `JIRA_API_TOKEN`       Jira API authentication token    `ATATT3xFfGF0...`

  `JIRA_DOMAIN`          Jira instance domain             `example.atlassian.net`
  `NOTION_API_KEY`       Notion integration token         `secret_xxx`

  `CHECK_INTERVAL`       Sync interval in seconds         `10`

  `LOG_FILE`             Log file path                    `app.log`
 
  `PROJECTS`             JSON list of project configs     `[{"key":"PROJ","jql":"project = PROJ"}]`
  ----------------------------------------------------------------------------------

`PROJECTS` holds project-specific settings (`key` and `jql`) in JSON
format. Each entry may optionally include `database_id`; if omitted, the
`NOTION_DATABASE_ID` environment variable is used for all projects.

```bash
PROJECTS='[
  {"key": "PROJ", "jql": "project = PROJ"},
  {"key": "ANOTHER", "database_id": "abcd1234...", "jql": "project = ANOTHER"}
]'
```
The `/sync-user-issues` endpoint processes every entry in this list and
returns an error if none are configured.

### Field mapping

Jira and Notion field names are linked in `app/field_map.yaml`.
Each entry defines a `jira_field: notion_property` pair used by the
Jira client to request fields and by the Notion client to build page
properties. Adjust this file to match your workspace. Any Notion
properties that do not exist in the target database are ignored during
page creation or updates to avoid API errors.

------------------------------------------------------------------------

## 🚀 Quick Start

### Requirements

-   Docker + Docker Compose\
-   Python 3.9+ (for local development)\
-   Valid Jira & Notion API credentials

### Development

``` bash
git clone https://github.com/diegomad14/jira2notion.git
cd jira2notion
cp .env.example .env   # configure your credentials
docker-compose up --build
```

Service will be available at: **http://localhost:8000**

### Production

``` bash
docker build -t jira2notion:latest .
docker run -d \
  --name jira2notion \
  -p 8000:8000 \
  --env-file .env \
  jira2notion:latest
```

------------------------------------------------------------------------

## 📡 REST Endpoints

  -----------------------------------------------------------------------------
  Method   Endpoint                  Description
  -------- ------------------------- ------------------------------------------
  `GET`    `/`                       Basic health check

  `GET`    `/status`                 Detailed system status (Jira/Notion
                                     connections, scheduler)

  `POST`   `/check-updated-issues`   Process updated Jira issues since last
                                     checkpoint

  `POST`   `/check-new-issues`       Process newly created issues

  `POST`   `/sync-user-issues`       Full synchronization of all user-assigned
                                     issues across configured projects
  -----------------------------------------------------------------------------

------------------------------------------------------------------------

## 🔍 Monitoring & Logs

-   Persistent logs: `app.log` (rotating, 1MB x 5 backups).\
-   Console logs for local debugging.\
-   Health checks at `/` and `/status`.

Key log patterns: - `Service started successfully` → successful
startup.\
- `Synchronizing issue: PROJ-173836` → active processing.\
- `Page successfully updated` → completed synchronization.

------------------------------------------------------------------------
