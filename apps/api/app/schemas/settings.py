from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    llm_consent: bool
    llm_consent_at: datetime | None


class SettingsUpdate(BaseModel):
    llm_consent: bool
