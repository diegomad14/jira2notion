from tinydb import TinyDB, Query
from typing import Optional

class StateManager:
    def __init__(self):
        self.db = TinyDB('state.json')
        self.table = self.db.table('last_processed')

    def get_last_key(self, project: str) -> Optional[str]:
        """Retrieve the last processed issue key for a project."""
        Project = Query()
        doc = self.table.get(Project.project == project)
        return doc['value'] if doc else None

    def update_last_key(self, project: str, key: str) -> None:
        """Update the last processed issue key for a project."""
        Project = Query()
        self.table.upsert({'project': project, 'value': key}, Project.project == project)
