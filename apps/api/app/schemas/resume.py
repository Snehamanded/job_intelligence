import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ResumeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    file_type: Literal["pdf", "docx", "txt"]
    size_bytes: int
    status: Literal["queued", "parsing", "parsed", "failed"]
    error_message: str | None
    parse_notice: str | None
    page_count: int | None
    parsed_at: datetime | None
    created_at: datetime
