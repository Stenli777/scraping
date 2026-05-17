from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class TaskCreate(BaseModel):
    source_url: HttpUrl
    parser_type: str = Field(default="generic_article")


class TaskRead(BaseModel):
    id: int
    source_id: int | None
    source_url: str
    status: str
    parser_type: str
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    document_id: int | None = None

    model_config = {"from_attributes": True}
