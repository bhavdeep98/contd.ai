"""
Webhook support for workflow events.
"""

from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum
import asyncio
import hashlib
import hmac
import json
import logging
import time
import secrets

logger = logging.getLogger(__name__)


class WebhookEvent(str, Enum):
    """Events that can trigger webhooks."""
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_PAUSED = "workflow.paused"
    WORKFLOW_RESUMED = "workflow.resumed"
    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    SAVEPOINT_CREATED = "savepoint.created"


class WebhookCreate(BaseModel):
    """Request model for creating a webhook."""
    url: HttpUrl
    events: List[WebhookEvent]
    secret: Optional[str] = None
    description: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    enabled: bool = True


class WebhookUpdate(BaseModel):
    """Request model for updating a webhook."""
    url: Optional[HttpUrl] = None
    events: Optional[List[WebhookEvent]] = None
    description: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    enabled: Optional[bool] = None


class Webhook(BaseModel):
    """Webhook configuration."""
    webhook_id: UUID
    org_id: UUID
    url: str
    events: List[WebhookEvent]
    secret_hash: str
    description: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    enabled: bool = True
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WebhookDelivery(BaseModel):
    """Record of a webhook delivery attempt."""
    delivery_id: UUID
    webhook_id: UUID
    event_type: WebhookEvent
    payload: Dict[str, Any]
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    duration_ms: Optional[int] = None
    success: bool = False
    attempt: int = 1
    created_at: datetime


class WebhookPayload(BaseModel):
    """Standard webhook payload structure."""
    event: WebhookEvent
    timestamp: datetime
    workflow_id: str
    org_id: str
    data: Dict[str, Any]


def generate_webhook_secret() -> str:
    """Generate a secure webhook secret."""
    return f"whsec_{secrets.token_urlsafe(32)}"


def compute_signature(payload: str, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload."""
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def verify_signature(payload: str, signature: str, secret: str) -> bool:
    """Verify webhook signature."""
    expected = compute_signature(payload, secret)
    return hmac.compare_digest(expected, signature)


class WebhookStore:
    """Storage for webhook configurations."""
    
    def __init__(self, db):
        self.db = db
    
    def create_webhook(
        self,
        org_id: str,
        url: str,
        events: List[WebhookEvent],
        secret: str,
        description: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Webhook:
        """Create a new webhook."""
        webhook_id = uuid4()
        now = datetime.utcnow()
        secret_hash = hashlib.sha256(secret.encode()).hexdigest()
        
        events_str = json.dumps([e.value for e in events])
        headers_str = json.dumps(headers) if headers else None
        
        self.db.execute(
            """INSERT INTO webhooks 
               (webhook_id, org_id, url, events, secret_hash, description, headers, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            str(webhook_id), str(org_id), url, events_str, secret_hash,
            description, headers_str, True, now, now
        )
        
        return Webhook(
            webhook_id=webhook_id,
            org_id=UUID(org_id),
            url=url,
            events=events,
            secret_hash=secret_hash,
            description=description,
            headers=headers,
            enabled=True,
            created_at=now,
            updated_at=now
        )
    
    def get_webhook(self, webhook_id: str, org_id: str) -> Optional[Webhook]:
        """Get a webhook by ID."""
        rows = self.db.query(
            "SELECT * FROM webhooks WHERE webhook_id = ? AND org_id = ?",
            str(webhook_id), str(org_id)
        )
        if not rows:
            return None
        
        row = rows[0]
        row['events'] = [WebhookEvent(e) for e in json.loads(row['events'])]
        row['headers'] = json.loads(row['headers']) if row.get('headers') else None
        return Webhook(**row)
    
    def list_webhooks(self, org_id: str) -> List[Webhook]:
        """List all webhooks for an organization."""
        rows = self.db.query(
            "SELECT * FROM webhooks WHERE org_id = ?",
            str(org_id)
        )
        
        webhooks = []
        for row in rows:
            row['events'] = [WebhookEvent(e) for e in json.loads(row['events'])]
            row['headers'] = json.loads(row['headers']) if row.get('headers') else None
            webhooks.append(Webhook(**row))
        
        return webhooks
    
    def get_webhooks_for_event(self, org_id: str, event: WebhookEvent) -> List[Webhook]:
        """Get all enabled webhooks subscribed to an event."""
        webhooks = self.list_webhooks(org_id)
        return [w for w in webhooks if w.enabled and event in w.events]
    
    def update_webhook(
        self,
        webhook_id: str,
        org_id: str,
        updates: WebhookUpdate
    ) -> Optional[Webhook]:
        """Update a webhook."""
        webhook = self.get_webhook(webhook_id, org_id)
        if not webhook:
            return None
        
        now = datetime.utcnow()
        update_fields = []
        update_values = []
        
        if updates.url is not None:
            update_fields.append("url = ?")
            update_values.append(str(updates.url))
        
        if updates.events is not None:
            update_fields.append("events = ?")
            update_values.append(json.dumps([e.value for e in updates.events]))
        
        if updates.description is not None:
            update_fields.append("description = ?")
            update_values.append(updates.description)
        
        if updates.headers is not None:
            update_fields.append("headers = ?")
            update_values.append(json.dumps(updates.headers))
        
        if updates.enabled is not None:
            update_fields.append("enabled = ?")
            update_values.append(updates.enabled)
        
        if update_fields:
            update_fields.append("updated_at = ?")
            update_values.append(now)
            
            sql = f"UPDATE webhooks SET {', '.join(update_fields)} WHERE webhook_id = ? AND org_id = ?"
            update_values.extend([str(webhook_id), str(org_id)])
            self.db.execute(sql, *update_values)
        
        return self.get_webhook(webhook_id, org_id)
    
    def delete_webhook(self, webhook_id: str, org_id: str) -> bool:
        """Delete a webhook."""
        self.db.execute(
            "DELETE FROM webhooks WHERE webhook_id = ? AND org_id = ?",
            str(webhook_id), str(org_id)
        )
        return True
    
    def record_delivery(self, delivery: WebhookDelivery):
        """Record a webhook delivery attempt."""
        self.db.execute(
            """INSERT INTO webhook_deliveries 
               (delivery_id, webhook_id, event_type, payload, response_status, 
                response_body, duration_ms, success, attempt, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            str(delivery.delivery_id), str(delivery.webhook_id), delivery.event_type.value,
            json.dumps(delivery.payload), delivery.response_status, delivery.response_body,
            delivery.duration_ms, delivery.success, delivery.attempt, delivery.created_at
        )


class WebhookDispatcher:
    """Handles dispatching webhooks with retries."""
    
    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 5, 30]
    TIMEOUT = 30
    
    def __init__(self, store: WebhookStore, secret_lookup: Dict[str, str] = None):
        self.store = store
        self._secret_lookup = secret_lookup or {}
        self._client = None
    
    async def _get_client(self):
        """Get or create HTTP client."""
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(timeout=self.TIMEOUT)
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _build_headers(
        self,
        webhook: Webhook,
        payload_str: str,
        secret: Optional[str] = None
    ) -> Dict[str, str]:
        """Build headers for webhook request."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Contd-Webhook/1.0",
            "X-Webhook-ID": str(webhook.webhook_id),
        }
        
        if secret:
            timestamp = str(int(time.time()))
            signature_payload = f"{timestamp}.{payload_str}"
            signature = compute_signature(signature_payload, secret)
            headers["X-Webhook-Timestamp"] = timestamp
            headers["X-Webhook-Signature"] = f"sha256={signature}"
        
        if webhook.headers:
            headers.update(webhook.headers)
        
        return headers
    
    async def dispatch(
        self,
        webhook: Webhook,
        event: WebhookEvent,
        workflow_id: str,
        org_id: str,
        data: Dict[str, Any],
        secret: Optional[str] = None
    ) -> WebhookDelivery:
        """Dispatch a webhook with retries."""
        payload = WebhookPayload(
            event=event,
            timestamp=datetime.utcnow(),
            workflow_id=workflow_id,
            org_id=org_id,
            data=data
        )
        
        payload_str = payload.model_dump_json()
        headers = self._build_headers(webhook, payload_str, secret)
        
        client = await self._get_client()
        delivery_id = uuid4()
        delivery = None
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            start_time = time.monotonic()
            
            try:
                response = await client.post(
                    webhook.url,
                    content=payload_str,
                    headers=headers
                )
                
                duration_ms = int((time.monotonic() - start_time) * 1000)
                success = 200 <= response.status_code < 300
                
                delivery = WebhookDelivery(
                    delivery_id=delivery_id,
                    webhook_id=webhook.webhook_id,
                    event_type=event,
                    payload=payload.model_dump(),
                    response_status=response.status_code,
                    response_body=response.text[:1000] if response.text else None,
                    duration_ms=duration_ms,
                    success=success,
                    attempt=attempt,
                    created_at=datetime.utcnow()
                )
                
                if success:
                    logger.info(f"Webhook delivered: {webhook.webhook_id} -> {event.value}")
                    self.store.record_delivery(delivery)
                    return delivery
                
                logger.warning(
                    f"Webhook failed: {webhook.webhook_id} status={response.status_code} attempt={attempt}"
                )
                
            except Exception as e:
                duration_ms = int((time.monotonic() - start_time) * 1000)
                logger.error(f"Webhook error: {webhook.webhook_id} error={e} attempt={attempt}")
                
                delivery = WebhookDelivery(
                    delivery_id=delivery_id,
                    webhook_id=webhook.webhook_id,
                    event_type=event,
                    payload=payload.model_dump(),
                    response_status=None,
                    response_body=str(e)[:1000],
                    duration_ms=duration_ms,
                    success=False,
                    attempt=attempt,
                    created_at=datetime.utcnow()
                )
            
            if attempt < self.MAX_RETRIES:
                await asyncio.sleep(self.RETRY_DELAYS[attempt - 1])
        
        if delivery:
            self.store.record_delivery(delivery)
        return delivery
    
    async def dispatch_event(
        self,
        org_id: str,
        event: WebhookEvent,
        workflow_id: str,
        data: Dict[str, Any]
    ):
        """Dispatch an event to all subscribed webhooks."""
        webhooks = self.store.get_webhooks_for_event(org_id, event)
        
        if not webhooks:
            return
        
        tasks = []
        for webhook in webhooks:
            secret = self._secret_lookup.get(str(webhook.webhook_id))
            tasks.append(
                self.dispatch(webhook, event, workflow_id, org_id, data, secret)
            )
        
        await asyncio.gather(*tasks, return_exceptions=True)


_dispatcher: Optional[WebhookDispatcher] = None


def get_webhook_dispatcher() -> Optional[WebhookDispatcher]:
    """Get the global webhook dispatcher."""
    return _dispatcher


def set_webhook_dispatcher(dispatcher: WebhookDispatcher):
    """Set the global webhook dispatcher."""
    global _dispatcher
    _dispatcher = dispatcher


async def emit_webhook_event(
    org_id: str,
    event: WebhookEvent,
    workflow_id: str,
    data: Dict[str, Any]
):
    """Emit a webhook event (convenience function)."""
    dispatcher = get_webhook_dispatcher()
    if dispatcher:
        await dispatcher.dispatch_event(org_id, event, workflow_id, data)
