import json
import os
from typing import List
from pydantic import BaseSettings, BaseModel, Field, validator


class ProjectConfig(BaseModel):
    key: str
    database_id: str
    jql: str

class Settings(BaseSettings):
    log_file: str = "app.log"
    jira_assignee: str = os.getenv("JIRA_EMAIL", None)
    check_interval: int = 10
    projects: List[ProjectConfig] = Field(default_factory=list)

    @validator("projects", pre=True)
    def load_projects_from_env(cls, v):  # type: ignore[override]
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError as exc:  # pragma: no cover - config error
                raise ValueError("Invalid JSON in PROJECTS environment variable") from exc
        return v

    class Config:
        env_file = ".env"
        env_prefix = ""
        fields = {"projects": {"env": "PROJECTS"}}

settings = Settings()

