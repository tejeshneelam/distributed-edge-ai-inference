"""
result_routes.py — API endpoints for submitting and retrieving inference results.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models import (
    AlertEvent,
    AggregatedResults,
    FrameResult,
    FrameResultRequest,
    InferenceResultRequest,
    SuccessResponse,
)
from backend.services import result_aggregator, worker_manager

router = APIRouter(tags=["Results"])


@router.post("/frame-result", response_model=SuccessResponse, status_code=201)
def submit_frame_result(req: FrameResultRequest):
    """
    Accept an inference result from a worker node (simplified REST flow).

    Stores the frame result keyed by frame_id; re-submitting the same
    frame_id overwrites the previous entry.
    """
    result = result_aggregator.add_frame_result(req)
    return SuccessResponse(
        message=f"Frame {req.frame_id} result stored (worker: '{req.worker_id}').",
        data=result,
    )


@router.post("/results", response_model=SuccessResponse, status_code=201)
def submit_inference_result(req: InferenceResultRequest):
    """Accept a full inference result with Detection objects (socket coordinator flow)."""
    if not worker_manager.get(req.worker_id):
        raise HTTPException(
            status_code=404,
            detail=f"Worker '{req.worker_id}' is not registered. Register it first.",
        )
    result = result_aggregator.add_result(req)
    return SuccessResponse(
        message=f"Result for frame {req.frame_id} stored successfully.",
        data=result,
    )


@router.get("/results/summary", summary="O(1) metrics snapshot — use this for dashboard polling")
def get_results_summary():
    """Return running totals without building the full frame list."""
    return result_aggregator.get_summary()


@router.get("/results", response_model=AggregatedResults)
def get_results():
    """Return aggregated detection statistics across all processed frames."""
    return result_aggregator.get_aggregated()


@router.get("/results/frames", response_model=list[FrameResult])
def list_frames():
    """Return per-frame detection results sorted by frame ID."""
    return result_aggregator.get_aggregated().frames


@router.get("/results/frames/{frame_id}", response_model=FrameResult)
def get_frame(frame_id: int):
    """Return detection results for a specific frame."""
    for fr in result_aggregator.get_aggregated().frames:
        if fr.frame_id == frame_id:
            return fr
    raise HTTPException(status_code=404, detail=f"Frame {frame_id} not found.")


# ── Alert routes ───────────────────────────────────────────────────────────────────

@router.post("/alerts", response_model=SuccessResponse, status_code=201)
def submit_alert(req: AlertEvent):
    """
    Accept a high-confidence alert event from an edge worker.
    Workers raise these autonomously — without waiting for the coordinator to poll.
    """
    result_aggregator.add_alert(req.model_dump(mode="json"))
    print(
        f"[coordinator] ALERT from '{req.worker_id}': "
        f"{req.alert_labels} (frame {req.frame_id})"
    )
    return SuccessResponse(message=f"Alert from '{req.worker_id}' recorded.")


@router.get("/alerts", summary="Recent high-confidence edge alerts, newest first")
def get_alerts():
    """Return all alert events raised by edge workers, newest first."""
    return result_aggregator.get_alerts()
