import os
from typing import List
from pydantic import BaseSettings, BaseModel


class ProjectConfig(BaseModel):
    key: str
    database_id: str
    jql: str

class Settings(BaseSettings):
    log_file: str = "app.log"
    jira_assignee: str = os.getenv("JIRA_EMAIL", None)
    check_interval: int = 10
    projects: List[ProjectConfig] = []

    class Config:
        env_file = ".env"

settings = Settings()

