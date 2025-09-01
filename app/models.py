# models.py
from typing import Optional
from pydantic import BaseModel

class JiraIssue(BaseModel):
    key: str
    summary: str
    description_rest: str
    status: str
    created: str
    reporter: Optional[dict]  # Cambié a Optional para permitir que sea None
    displayName: Optional[str]  # También Optional para manejar valores faltantes
    description_adv: Optional[dict]  # Igual que los demás, Optional