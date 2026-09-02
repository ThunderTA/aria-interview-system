from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from app.core.deps import get_current_user
from app.models.session import SessionCreate, SessionOut

router = APIRouter(prefix="/sessions", tags=["sessions"])

# TODO(owner: RL + ASR + LLM workstreams): wire this up to
# app/services/rl_engine.py (difficulty selection), app/services/asr.py
# (Whisper transcription) and app/services/llm_judge.py (question
# generation + answer scoring) per docs/architecture.md.


@router.post("", response_model=SessionOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_session(payload: SessionCreate, current_user: dict = Depends(get_current_user)):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Session creation not yet implemented")


@router.get("", response_model=list[SessionOut])
async def list_sessions(current_user: dict = Depends(get_current_user)):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Session history not yet implemented")


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Session detail not yet implemented")


@router.delete("/{session_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Session deletion not yet implemented")


@router.post("/{session_id}/end", response_model=SessionOut)
async def end_session(session_id: str, current_user: dict = Depends(get_current_user)):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Session finalization not yet implemented")


@router.get("/{session_id}/report")
async def get_report(session_id: str, current_user: dict = Depends(get_current_user)):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Report generation not yet implemented")


@router.websocket("/{session_id}/stream")
async def interview_stream(websocket: WebSocket, session_id: str):
    """
    Live interview loop: client streams audio chunks + sampled video frames,
    server pushes back partial transcript / gaze signal / next question.

    TODO: implement VAD-based utterance segmentation -> Whisper -> LLM
    judge -> RL difficulty selection -> next question, per
    docs/architecture.md ("Real-Time Interview Loop"). This handler only
    proves the route is reachable so far.
    """
    await websocket.accept()
    try:
        await websocket.send_json(
            {"type": "not_implemented", "detail": "Real-time interview loop not yet implemented"}
        )
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()
