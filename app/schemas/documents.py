from datetime import datetime

from pydantic import BaseModel


class DocumentRead(BaseModel):
    id: int
    task_id: int
    source_url: str
    content_hash: str
    raw_text: str | None
    clean_text: str | None
    rewritten_text: str | None
    version: int
    metadata_json: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
