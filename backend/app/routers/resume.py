from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from pymongo import ReturnDocument

from app.core.deps import get_current_user
from app.db.mongodb import get_db
from app.models.resume import ResumeOut
from app.services.resume_parser import MAX_RESUME_BYTES, ResumeParseError, parse_resume

router = APIRouter(prefix="/resume", tags=["resume"])

ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt"}


class ResumeUpdate(BaseModel):
    """Lets the candidate correct what the parser inferred."""

    inferred_role: str | None = None
    inferred_level: str | None = None


def _to_out(doc: dict) -> ResumeOut:
    return ResumeOut(
        id=str(doc["_id"]),
        user_id=doc["user_id"],
        raw_text=doc["raw_text"],
        parsed_skills=doc.get("parsed_skills", []),
        inferred_role=doc.get("inferred_role"),
        inferred_level=doc.get("inferred_level"),
        uploaded_at=doc["uploaded_at"],
    )


@router.post("/upload", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Parse an uploaded resume and store it as this user's current resume."""
    filename = file.filename or ""
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Upload a PDF or Word document (.pdf, .docx).",
        )

    content = await file.read()
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Resume is too large (max {MAX_RESUME_BYTES // (1024 * 1024)} MB).",
        )

    try:
        parsed = parse_resume(filename, content)
    except ResumeParseError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    user_id = str(current_user["_id"])
    doc = {
        **parsed,
        "user_id": user_id,
        "uploaded_at": datetime.now(timezone.utc),
    }

    # One current resume per user — a new upload replaces the previous one.
    result = await db.resumes.find_one_and_replace(
        {"user_id": user_id}, doc, upsert=True, return_document=ReturnDocument.AFTER
    )
    return _to_out(result)


@router.get("", response_model=ResumeOut)
async def get_resume(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    doc = await db.resumes.find_one({"user_id": str(current_user["_id"])})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No resume uploaded yet.")
    return _to_out(doc)


@router.patch("", response_model=ResumeOut)
async def update_resume(
    payload: ResumeUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update.")

    doc = await db.resumes.find_one_and_update(
        {"user_id": str(current_user["_id"])}, {"$set": updates}, return_document=ReturnDocument.AFTER
    )
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No resume uploaded yet.")
    return _to_out(doc)
