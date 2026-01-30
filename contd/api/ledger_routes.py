"""
API routes for ledger visualization and human-in-the-loop review.

Provides endpoints to:
- View reasoning traces and annotations
- Review and approve/reject reasoning steps
- Visualize the ledger timeline
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
import logging

from contd.core.engine import ExecutionEngine
from contd.api.dependencies import get_auth_context, AuthContext

router = APIRouter(prefix="/v1/workflows/{workflow_id}/ledger", tags=["ledger"])
logger = logging.getLogger(__name__)


# --- Models ---

class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class AnnotationView(BaseModel):
    step_number: int
    step_name: str
    timestamp: str
    text: str


class DigestView(BaseModel):
    digest_id: str
    step_number: int
    timestamp: str
    payload: Dict[str, Any]
    raw_chunk_count: int
    raw_byte_count: int


class StepSignalView(BaseModel):
    step_number: int
    step_name: str
    output_bytes: int
    duration_ms: int
    was_retry: bool
    timestamp: str


class ReasoningTraceView(BaseModel):
    """Complete reasoning trace for a workflow step."""
    step_number: int
    step_name: str
    annotation: Optional[AnnotationView] = None
    raw_reasoning: Optional[List[str]] = None
    digest: Optional[DigestView] = None
    signal: Optional[StepSignalView] = None
    review_status: ReviewStatus = ReviewStatus.PENDING


class LedgerSummary(BaseModel):
    """High-level ledger statistics."""
    workflow_id: str
    total_steps: int
    total_annotations: int
    total_digests: int
    total_context_bytes: int
    undigested_bytes: int
    pending_reviews: int


class LedgerTimeline(BaseModel):
    """Timeline view of all ledger entries."""
    workflow_id: str
    entries: List[Dict[str, Any]]
    summary: LedgerSummary


class ReviewRequest(BaseModel):
    """Request to review a reasoning step."""
    status: ReviewStatus
    feedback: Optional[str] = None
    suggested_revision: Optional[str] = None


class ReviewResponse(BaseModel):
    step_number: int
    status: ReviewStatus
    reviewed_at: str
    reviewer_feedback: Optional[str] = None


# In-memory review store (would be persisted in production)
_reviews: Dict[str, Dict[int, ReviewResponse]] = {}


# --- Endpoints ---

@router.get("/summary", response_model=LedgerSummary)
async def get_ledger_summary(
    workflow_id: str,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Get high-level summary of the reasoning ledger."""
    engine = ExecutionEngine.get_instance()
    
    try:
        state, _ = engine.restore(workflow_id, org_id=ctx.org_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {e}")
    
    # Get ledger from state metadata
    ledger_data = state.metadata.get("reasoning_ledger", {})
    
    annotations = ledger_data.get("annotations", [])
    digests = ledger_data.get("digests", [])
    raw_buffer_bytes = ledger_data.get("raw_buffer_bytes", 0)
    
    # Count pending reviews
    workflow_reviews = _reviews.get(workflow_id, {})
    pending = sum(1 for r in workflow_reviews.values() if r.status == ReviewStatus.PENDING)
    
    return LedgerSummary(
        workflow_id=workflow_id,
        total_steps=state.step_number,
        total_annotations=len(annotations),
        total_digests=len(digests),
        total_context_bytes=_calculate_context_bytes(ledger_data),
        undigested_bytes=raw_buffer_bytes,
        pending_reviews=pending,
    )


@router.get("/timeline", response_model=LedgerTimeline)
async def get_ledger_timeline(
    workflow_id: str,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Get chronological timeline of all ledger entries for visualization."""
    engine = ExecutionEngine.get_instance()
    
    try:
        state, _ = engine.restore(workflow_id, org_id=ctx.org_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {e}")
    
    ledger_data = state.metadata.get("reasoning_ledger", {})
    entries = []
    
    # Collect all entries with timestamps
    for ann in ledger_data.get("annotations", []):
        entries.append({
            "type": "annotation",
            "timestamp": ann.get("timestamp"),
            "step_number": ann.get("step_number"),
            "step_name": ann.get("step_name"),
            "content": ann.get("text"),
        })
    
    for digest in ledger_data.get("digests", []):
        entries.append({
            "type": "digest",
            "timestamp": digest.get("timestamp"),
            "step_number": digest.get("step_number"),
            "digest_id": digest.get("digest_id"),
            "payload": digest.get("payload"),
            "compression_ratio": _calc_compression_ratio(digest),
        })
    
    # Sort by timestamp
    entries.sort(key=lambda x: x.get("timestamp", ""))
    
    # Add review status to each entry
    workflow_reviews = _reviews.get(workflow_id, {})
    for entry in entries:
        step_num = entry.get("step_number")
        if step_num in workflow_reviews:
            entry["review_status"] = workflow_reviews[step_num].status
        else:
            entry["review_status"] = ReviewStatus.PENDING
    
    summary = await get_ledger_summary(workflow_id, ctx)
    
    return LedgerTimeline(
        workflow_id=workflow_id,
        entries=entries,
        summary=summary,
    )


@router.get("/traces", response_model=List[ReasoningTraceView])
async def get_reasoning_traces(
    workflow_id: str,
    step_number: Optional[int] = None,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Get detailed reasoning traces, optionally filtered by step."""
    engine = ExecutionEngine.get_instance()
    
    try:
        state, _ = engine.restore(workflow_id, org_id=ctx.org_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {e}")
    
    ledger_data = state.metadata.get("reasoning_ledger", {})
    traces = _build_traces(ledger_data, workflow_id)
    
    if step_number is not None:
        traces = [t for t in traces if t.step_number == step_number]
    
    return traces


@router.get("/traces/{step_number}", response_model=ReasoningTraceView)
async def get_step_trace(
    workflow_id: str,
    step_number: int,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Get detailed reasoning trace for a specific step."""
    traces = await get_reasoning_traces(workflow_id, step_number, ctx)
    
    if not traces:
        raise HTTPException(status_code=404, detail=f"No trace found for step {step_number}")
    
    return traces[0]


@router.post("/traces/{step_number}/review", response_model=ReviewResponse)
async def review_step(
    workflow_id: str,
    step_number: int,
    request: ReviewRequest,
    ctx: AuthContext = Depends(get_auth_context),
):
    """
    Submit human review for a reasoning step.
    
    This enables human-in-the-loop oversight of agent reasoning.
    """
    # Verify workflow exists
    engine = ExecutionEngine.get_instance()
    try:
        engine.restore(workflow_id, org_id=ctx.org_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {e}")
    
    # Store review
    if workflow_id not in _reviews:
        _reviews[workflow_id] = {}
    
    review = ReviewResponse(
        step_number=step_number,
        status=request.status,
        reviewed_at=datetime.utcnow().isoformat(),
        reviewer_feedback=request.feedback,
    )
    
    _reviews[workflow_id][step_number] = review
    
    logger.info(f"Step {step_number} of workflow {workflow_id} reviewed: {request.status}")
    
    # If rejected, could trigger workflow pause/rollback
    if request.status == ReviewStatus.REJECTED:
        logger.warning(f"Step {step_number} rejected - workflow may need intervention")
    
    return review


@router.get("/reviews", response_model=List[ReviewResponse])
async def get_reviews(
    workflow_id: str,
    status: Optional[ReviewStatus] = None,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Get all reviews for a workflow, optionally filtered by status."""
    workflow_reviews = _reviews.get(workflow_id, {})
    reviews = list(workflow_reviews.values())
    
    if status:
        reviews = [r for r in reviews if r.status == status]
    
    return reviews


@router.get("/undigested", response_model=Dict[str, Any])
async def get_undigested_reasoning(
    workflow_id: str,
    ctx: AuthContext = Depends(get_auth_context),
):
    """Get raw undigested reasoning buffer for review."""
    engine = ExecutionEngine.get_instance()
    
    try:
        state, _ = engine.restore(workflow_id, org_id=ctx.org_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {e}")
    
    ledger_data = state.metadata.get("reasoning_ledger", {})
    
    return {
        "workflow_id": workflow_id,
        "raw_buffer": ledger_data.get("raw_buffer", []),
        "raw_buffer_bytes": ledger_data.get("raw_buffer_bytes", 0),
        "chunks_count": len(ledger_data.get("raw_buffer", [])),
    }


# --- Helper Functions ---

def _calculate_context_bytes(ledger_data: dict) -> int:
    """Calculate total context bytes from ledger data."""
    annotation_bytes = sum(
        len(a.get("text", "").encode("utf-8")) 
        for a in ledger_data.get("annotations", [])
    )
    digest_bytes = sum(
        len(str(d.get("payload", {})).encode("utf-8"))
        for d in ledger_data.get("digests", [])
    )
    raw_bytes = ledger_data.get("raw_buffer_bytes", 0)
    return annotation_bytes + digest_bytes + raw_bytes


def _calc_compression_ratio(digest: dict) -> float:
    """Calculate compression ratio for a digest."""
    raw_bytes = digest.get("raw_byte_count", 0)
    if raw_bytes == 0:
        return 0.0
    payload_bytes = len(str(digest.get("payload", {})).encode("utf-8"))
    return round(raw_bytes / max(payload_bytes, 1), 2)


def _build_traces(ledger_data: dict, workflow_id: str) -> List[ReasoningTraceView]:
    """Build reasoning traces from ledger data."""
    traces_by_step: Dict[int, ReasoningTraceView] = {}
    workflow_reviews = _reviews.get(workflow_id, {})
    
    # Process annotations
    for ann in ledger_data.get("annotations", []):
        step_num = ann.get("step_number", 0)
        if step_num not in traces_by_step:
            traces_by_step[step_num] = ReasoningTraceView(
                step_number=step_num,
                step_name=ann.get("step_name", f"step_{step_num}"),
            )
        traces_by_step[step_num].annotation = AnnotationView(
            step_number=ann.get("step_number"),
            step_name=ann.get("step_name"),
            timestamp=ann.get("timestamp"),
            text=ann.get("text"),
        )
    
    # Process digests
    for digest in ledger_data.get("digests", []):
        step_num = digest.get("step_number", 0)
        if step_num not in traces_by_step:
            traces_by_step[step_num] = ReasoningTraceView(
                step_number=step_num,
                step_name=f"step_{step_num}",
            )
        traces_by_step[step_num].digest = DigestView(
            digest_id=digest.get("digest_id"),
            step_number=digest.get("step_number"),
            timestamp=digest.get("timestamp"),
            payload=digest.get("payload"),
            raw_chunk_count=digest.get("raw_chunk_count"),
            raw_byte_count=digest.get("raw_byte_count"),
        )
    
    # Add review status
    for step_num, trace in traces_by_step.items():
        if step_num in workflow_reviews:
            trace.review_status = workflow_reviews[step_num].status
    
    return sorted(traces_by_step.values(), key=lambda t: t.step_number)
