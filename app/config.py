# config.py
import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    log_file: str = "app.log"
    jira_assignee: str = os.getenv("JIRA_EMAIL", None)
    check_interval: int = 10

    class Config:
        env_file = ".env"

settings = Settings()
