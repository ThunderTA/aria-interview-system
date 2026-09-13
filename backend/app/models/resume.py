from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.identity import ResumePhotoOut


class ParsedSkill(BaseModel):
    name: str
    category: str | None = None


class ResumeOut(BaseModel):
    id: str
    user_id: str
    raw_text: str
    parsed_skills: list[ParsedSkill] = Field(default_factory=list)
    inferred_role: str | None = None
    inferred_level: str | None = None
    photo: ResumePhotoOut | None = None
    uploaded_at: datetime


class ResumeInDB(BaseModel):
    user_id: str
    raw_text: str
    parsed_skills: list[ParsedSkill] = Field(default_factory=list)
    inferred_role: str | None = None
    inferred_level: str | None = None
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
