from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.core.deps import get_current_user
from app.models.resume import ResumeOut

router = APIRouter(prefix="/resume", tags=["resume"])

# TODO(owner: resume-parsing workstream): parse the uploaded file with a
# resume parser (e.g. pyresparser / spaCy / LLM-based extraction) to infer
# role, seniority, skills and projects per docs/architecture.md. Persist
# into the `resumes` collection (see app/models/resume.py).


@router.post("/upload", response_model=ResumeOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def upload_resume(file: UploadFile, current_user: dict = Depends(get_current_user)):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Resume parsing not yet implemented")


@router.get("", response_model=ResumeOut)
async def get_resume(current_user: dict = Depends(get_current_user)):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Resume parsing not yet implemented")


@router.patch("", response_model=ResumeOut)
async def update_resume(current_user: dict = Depends(get_current_user)):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Resume parsing not yet implemented")
