"""
Webhook management API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from contd.api.webhooks import (
    WebhookCreate, WebhookUpdate, Webhook, WebhookEvent,
    WebhookStore, WebhookDelivery, generate_webhook_secret
)
from contd.api.dependencies import get_auth_context, AuthContext, get_db
from contd.core.engine import ExecutionEngine
import hashlib

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


async def get_webhook_store(db=Depends(get_db)):
    """Get webhook store dependency."""
    return WebhookStore(db)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    webhook_in: WebhookCreate,
    ctx: AuthContext = Depends(get_auth_context),
    store: WebhookStore = Depends(get_webhook_store)
):
    """
    Create a new webhook.
    
    The webhook will be called when any of the specified events occur.
    A secret will be generated if not provided - save it securely as it
    cannot be retrieved later.
    """
    secret = webhook_in.secret or generate_webhook_secret()
    
    webhook = store.create_webhook(
        org_id=ctx.org_id,
        url=str(webhook_in.url),
        events=webhook_in.events,
        secret=secret,
        description=webhook_in.description,
        headers=webhook_in.headers
    )
    
    # Return webhook with secret (only time it's visible)
    response = {
        "webhook_id": str(webhook.webhook_id),
        "url": webhook.url,
        "events": [e.value for e in webhook.events],
        "description": webhook.description,
        "enabled": webhook.enabled,
        "created_at": webhook.created_at.isoformat(),
        "secret": secret  # Only returned on creation
    }
    
    return response


@router.get("", response_model=List[dict])
async def list_webhooks(
    ctx: AuthContext = Depends(get_auth_context),
    store: WebhookStore = Depends(get_webhook_store)
):
    """List all webhooks for the organization."""
    webhooks = store.list_webhooks(ctx.org_id)
    
    return [
        {
            "webhook_id": str(w.webhook_id),
            "url": w.url,
            "events": [e.value for e in w.events],
            "description": w.description,
            "enabled": w.enabled,
            "created_at": w.created_at.isoformat(),
            "updated_at": w.updated_at.isoformat()
        }
        for w in webhooks
    ]


@router.get("/{webhook_id}", response_model=dict)
async def get_webhook(
    webhook_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    store: WebhookStore = Depends(get_webhook_store)
):
    """Get a specific webhook."""
    webhook = store.get_webhook(webhook_id, ctx.org_id)
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return {
        "webhook_id": str(webhook.webhook_id),
        "url": webhook.url,
        "events": [e.value for e in webhook.events],
        "description": webhook.description,
        "headers": webhook.headers,
        "enabled": webhook.enabled,
        "created_at": webhook.created_at.isoformat(),
        "updated_at": webhook.updated_at.isoformat()
    }


@router.patch("/{webhook_id}", response_model=dict)
async def update_webhook(
    webhook_id: str,
    updates: WebhookUpdate,
    ctx: AuthContext = Depends(get_auth_context),
    store: WebhookStore = Depends(get_webhook_store)
):
    """Update a webhook."""
    webhook = store.update_webhook(webhook_id, ctx.org_id, updates)
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return {
        "webhook_id": str(webhook.webhook_id),
        "url": webhook.url,
        "events": [e.value for e in webhook.events],
        "description": webhook.description,
        "headers": webhook.headers,
        "enabled": webhook.enabled,
        "created_at": webhook.created_at.isoformat(),
        "updated_at": webhook.updated_at.isoformat()
    }


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    store: WebhookStore = Depends(get_webhook_store)
):
    """Delete a webhook."""
    webhook = store.get_webhook(webhook_id, ctx.org_id)
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    store.delete_webhook(webhook_id, ctx.org_id)


@router.post("/{webhook_id}/test", response_model=dict)
async def test_webhook(
    webhook_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    store: WebhookStore = Depends(get_webhook_store)
):
    """
    Send a test event to a webhook.
    
    This sends a test payload to verify the webhook is configured correctly.
    """
    from contd.api.webhooks import WebhookDispatcher, WebhookEvent
    
    webhook = store.get_webhook(webhook_id, ctx.org_id)
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    dispatcher = WebhookDispatcher(store)
    
    try:
        delivery = await dispatcher.dispatch(
            webhook=webhook,
            event=WebhookEvent.WORKFLOW_STARTED,
            workflow_id="test-workflow-id",
            org_id=ctx.org_id,
            data={
                "test": True,
                "message": "This is a test webhook delivery"
            }
        )
        
        return {
            "success": delivery.success,
            "status_code": delivery.response_status,
            "duration_ms": delivery.duration_ms,
            "response_preview": delivery.response_body[:200] if delivery.response_body else None
        }
    finally:
        await dispatcher.close()


@router.get("/{webhook_id}/deliveries", response_model=List[dict])
async def list_webhook_deliveries(
    webhook_id: str,
    limit: int = 20,
    ctx: AuthContext = Depends(get_auth_context),
    store: WebhookStore = Depends(get_webhook_store)
):
    """
    List recent delivery attempts for a webhook.
    
    Useful for debugging webhook issues.
    """
    webhook = store.get_webhook(webhook_id, ctx.org_id)
    
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    # Query deliveries (would need to add this method to store)
    rows = store.db.query(
        """SELECT * FROM webhook_deliveries 
           WHERE webhook_id = ? 
           ORDER BY created_at DESC 
           LIMIT ?""",
        str(webhook_id), limit
    )
    
    return [
        {
            "delivery_id": str(row["delivery_id"]),
            "event_type": row["event_type"],
            "success": row["success"],
            "status_code": row["response_status"],
            "duration_ms": row["duration_ms"],
            "attempt": row["attempt"],
            "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], 'isoformat') else str(row["created_at"])
        }
        for row in rows
    ]


@router.get("/events/types", response_model=List[dict])
async def list_event_types():
    """List all available webhook event types."""
    return [
        {
            "event": event.value,
            "description": _get_event_description(event)
        }
        for event in WebhookEvent
    ]


def _get_event_description(event: WebhookEvent) -> str:
    """Get human-readable description for an event type."""
    descriptions = {
        WebhookEvent.WORKFLOW_STARTED: "Triggered when a workflow execution begins",
        WebhookEvent.WORKFLOW_COMPLETED: "Triggered when a workflow completes successfully",
        WebhookEvent.WORKFLOW_FAILED: "Triggered when a workflow fails with an error",
        WebhookEvent.WORKFLOW_PAUSED: "Triggered when a workflow is paused",
        WebhookEvent.WORKFLOW_RESUMED: "Triggered when a paused workflow is resumed",
        WebhookEvent.STEP_STARTED: "Triggered when a workflow step begins execution",
        WebhookEvent.STEP_COMPLETED: "Triggered when a workflow step completes",
        WebhookEvent.STEP_FAILED: "Triggered when a workflow step fails",
        WebhookEvent.SAVEPOINT_CREATED: "Triggered when a savepoint is created",
    }
    return descriptions.get(event, "No description available")
