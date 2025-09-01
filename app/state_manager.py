from tinydb import TinyDB, Query
from typing import Optional

class StateManager:
    def __init__(self):
        self.db = TinyDB('state.json')
        self.table = self.db.table('last_processed')
        
    def get_last_key(self) -> Optional[str]:
        """Retrieve the last processed issue key."""
        doc = self.table.get(doc_id=1)
        return doc['value'] if doc else None

    def update_last_key(self, key: str) -> None:
        """Update the last processed issue key."""
        self.table.upsert({'value': key}, doc_ids=[1])
