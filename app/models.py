from typing import Optional
from pydantic import BaseModel

class JiraIssue(BaseModel):
    key: str
    summary: str
    description_rest: str
    status: str
    created: str
    reporter: Optional[dict]
    displayName: Optional[str]
    emailAddress: Optional[str]
    description_adv: Optional[dict]
