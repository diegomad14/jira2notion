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

  `JIRA_PROJECT_KEY`     Jira project identifier          `PROJ`

  `NOTION_API_KEY`       Notion integration token         `secret_xxx`

  `NOTION_DATABASE_ID`   Target Notion database ID        `a1841d5b...`

  `CHECK_INTERVAL`       Sync interval in seconds         `10`

  `LOG_FILE`             Log file path                    `app.log`
  ----------------------------------------------------------------------------------

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
                                     issues
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
