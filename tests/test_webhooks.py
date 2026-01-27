"""Tests for webhook functionality."""

import pytest
import asyncio
import json
import hashlib
import hmac
import time
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from uuid import uuid4

from contd.api.webhooks import (
    WebhookEvent,
    WebhookCreate,
    WebhookUpdate,
    Webhook,
    WebhookDelivery,
    WebhookPayload,
    WebhookStore,
    WebhookDispatcher,
    generate_webhook_secret,
    compute_signature,
    verify_signature,
    emit_webhook_event,
    set_webhook_dispatcher,
    get_webhook_dispatcher
)


class TestWebhookSecret:
    """Tests for webhook secret generation and verification."""
    
    def test_generate_secret(self):
        """Generates a valid webhook secret."""
        secret = generate_webhook_secret()
        assert secret.startswith("whsec_")
        assert len(secret) > 20
    
    def test_generate_unique_secrets(self):
        """Each generated secret is unique."""
        secrets = [generate_webhook_secret() for _ in range(10)]
        assert len(set(secrets)) == 10
    
    def test_compute_signature(self):
        """Computes HMAC-SHA256 signature."""
        payload = '{"test": "data"}'
        secret = "test_secret"
        
        signature = compute_signature(payload, secret)
        
        # Verify it's a valid hex string
        assert len(signature) == 64
        int(signature, 16)  # Should not raise
    
    def test_verify_signature_valid(self):
        """Verifies valid signature."""
        payload = '{"test": "data"}'
        secret = "test_secret"
        signature = compute_signature(payload, secret)
        
        assert verify_signature(payload, signature, secret) is True
    
    def test_verify_signature_invalid(self):
        """Rejects invalid signature."""
        payload = '{"test": "data"}'
        secret = "test_secret"
        
        assert verify_signature(payload, "invalid_signature", secret) is False
    
    def test_verify_signature_wrong_secret(self):
        """Rejects signature with wrong secret."""
        payload = '{"test": "data"}'
        signature = compute_signature(payload, "secret1")
        
        assert verify_signature(payload, signature, "secret2") is False


class TestWebhookStore:
    """Tests for WebhookStore."""
    
    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.query.return_value = []
        return db
    
    @pytest.fixture
    def store(self, mock_db):
        return WebhookStore(mock_db)
    
    def test_create_webhook(self, store, mock_db):
        """Creates a webhook."""
        org_id = str(uuid4())
        webhook = store.create_webhook(
            org_id=org_id,
            url="https://example.com/webhook",
            events=[WebhookEvent.WORKFLOW_COMPLETED],
            secret="test_secret",
            description="Test webhook"
        )
        
        assert webhook.url == "https://example.com/webhook"
        assert WebhookEvent.WORKFLOW_COMPLETED in webhook.events
        assert webhook.description == "Test webhook"
        assert webhook.enabled is True
        
        mock_db.execute.assert_called_once()
    
    def test_get_webhook(self, store, mock_db):
        """Gets a webhook by ID."""
        webhook_id = str(uuid4())
        org_id = str(uuid4())
        
        mock_db.query.return_value = [{
            "webhook_id": webhook_id,
            "org_id": org_id,
            "url": "https://example.com/webhook",
            "events": '["workflow.completed"]',
            "secret_hash": "hash123",
            "description": "Test",
            "headers": None,
            "enabled": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }]
        
        webhook = store.get_webhook(webhook_id, org_id)
        
        assert webhook is not None
        assert webhook.url == "https://example.com/webhook"
        assert WebhookEvent.WORKFLOW_COMPLETED in webhook.events
    
    def test_get_webhook_not_found(self, store, mock_db):
        """Returns None for non-existent webhook."""
        mock_db.query.return_value = []
        
        webhook = store.get_webhook("nonexistent", "org-123")
        
        assert webhook is None
    
    def test_list_webhooks(self, store, mock_db):
        """Lists webhooks for an organization."""
        org_id = str(uuid4())
        
        mock_db.query.return_value = [
            {
                "webhook_id": str(uuid4()),
                "org_id": org_id,
                "url": "https://example.com/webhook1",
                "events": '["workflow.completed"]',
                "secret_hash": "hash1",
                "description": None,
                "headers": None,
                "enabled": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "webhook_id": str(uuid4()),
                "org_id": org_id,
                "url": "https://example.com/webhook2",
                "events": '["workflow.failed"]',
                "secret_hash": "hash2",
                "description": None,
                "headers": None,
                "enabled": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]
        
        webhooks = store.list_webhooks(org_id)
        
        assert len(webhooks) == 2
    
    def test_get_webhooks_for_event(self, store, mock_db):
        """Gets enabled webhooks for a specific event."""
        org_id = str(uuid4())
        
        mock_db.query.return_value = [
            {
                "webhook_id": str(uuid4()),
                "org_id": org_id,
                "url": "https://example.com/webhook1",
                "events": '["workflow.completed", "workflow.failed"]',
                "secret_hash": "hash1",
                "description": None,
                "headers": None,
                "enabled": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "webhook_id": str(uuid4()),
                "org_id": org_id,
                "url": "https://example.com/webhook2",
                "events": '["workflow.started"]',
                "secret_hash": "hash2",
                "description": None,
                "headers": None,
                "enabled": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]
        
        webhooks = store.get_webhooks_for_event(org_id, WebhookEvent.WORKFLOW_COMPLETED)
        
        assert len(webhooks) == 1
        assert webhooks[0].url == "https://example.com/webhook1"
    
    def test_delete_webhook(self, store, mock_db):
        """Deletes a webhook."""
        result = store.delete_webhook("webhook-123", "org-123")
        
        assert result is True
        mock_db.execute.assert_called_once()


class TestWebhookDispatcher:
    """Tests for WebhookDispatcher."""
    
    @pytest.fixture
    def mock_store(self):
        store = MagicMock(spec=WebhookStore)
        store.record_delivery = MagicMock()
        return store
    
    @pytest.fixture
    def dispatcher(self, mock_store):
        return WebhookDispatcher(mock_store)
    
    @pytest.fixture
    def sample_webhook(self):
        return Webhook(
            webhook_id=uuid4(),
            org_id=uuid4(),
            url="https://example.com/webhook",
            events=[WebhookEvent.WORKFLOW_COMPLETED],
            secret_hash="hash123",
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    @pytest.mark.asyncio
    async def test_dispatch_success(self, dispatcher, mock_store, sample_webhook):
        """Successfully dispatches webhook."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"received": true}'
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            dispatcher._client = mock_client
            
            delivery = await dispatcher.dispatch(
                webhook=sample_webhook,
                event=WebhookEvent.WORKFLOW_COMPLETED,
                workflow_id="wf-123",
                org_id="org-123",
                data={"result": "success"}
            )
            
            assert delivery.success is True
            assert delivery.response_status == 200
    
    @pytest.mark.asyncio
    async def test_dispatch_failure(self, dispatcher, mock_store, sample_webhook):
        """Handles webhook delivery failure."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = 'Internal Server Error'
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            dispatcher._client = mock_client
            dispatcher.MAX_RETRIES = 1  # Reduce retries for test
            
            delivery = await dispatcher.dispatch(
                webhook=sample_webhook,
                event=WebhookEvent.WORKFLOW_COMPLETED,
                workflow_id="wf-123",
                org_id="org-123",
                data={"result": "success"}
            )
            
            assert delivery.success is False
    
    @pytest.mark.asyncio
    async def test_build_headers_with_signature(self, dispatcher, sample_webhook):
        """Builds headers with signature when secret provided."""
        payload = '{"test": "data"}'
        secret = "test_secret"
        
        headers = dispatcher._build_headers(sample_webhook, payload, secret)
        
        assert "Content-Type" in headers
        assert "X-Webhook-ID" in headers
        assert "X-Webhook-Timestamp" in headers
        assert "X-Webhook-Signature" in headers
        assert headers["X-Webhook-Signature"].startswith("sha256=")
    
    @pytest.mark.asyncio
    async def test_build_headers_without_signature(self, dispatcher, sample_webhook):
        """Builds headers without signature when no secret."""
        payload = '{"test": "data"}'
        
        headers = dispatcher._build_headers(sample_webhook, payload, None)
        
        assert "Content-Type" in headers
        assert "X-Webhook-ID" in headers
        assert "X-Webhook-Signature" not in headers
    
    @pytest.mark.asyncio
    async def test_build_headers_with_custom_headers(self, dispatcher):
        """Includes custom headers from webhook config."""
        webhook = Webhook(
            webhook_id=uuid4(),
            org_id=uuid4(),
            url="https://example.com/webhook",
            events=[WebhookEvent.WORKFLOW_COMPLETED],
            secret_hash="hash123",
            headers={"X-Custom-Header": "custom-value"},
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        headers = dispatcher._build_headers(webhook, '{}', None)
        
        assert headers["X-Custom-Header"] == "custom-value"
    
    @pytest.mark.asyncio
    async def test_close_client(self, dispatcher):
        """Closes HTTP client."""
        mock_client = AsyncMock()
        dispatcher._client = mock_client
        
        await dispatcher.close()
        
        mock_client.aclose.assert_called_once()
        assert dispatcher._client is None


class TestWebhookPayload:
    """Tests for WebhookPayload model."""
    
    def test_payload_serialization(self):
        """Payload serializes to JSON."""
        payload = WebhookPayload(
            event=WebhookEvent.WORKFLOW_COMPLETED,
            timestamp=datetime.utcnow(),
            workflow_id="wf-123",
            org_id="org-456",
            data={"result": "success", "duration": 1234}
        )
        
        json_str = payload.json()
        parsed = json.loads(json_str)
        
        assert parsed["event"] == "workflow.completed"
        assert parsed["workflow_id"] == "wf-123"
        assert parsed["data"]["result"] == "success"


class TestWebhookEvents:
    """Tests for WebhookEvent enum."""
    
    def test_all_events_have_values(self):
        """All events have string values."""
        for event in WebhookEvent:
            assert isinstance(event.value, str)
            assert "." in event.value  # Format: category.action
    
    def test_event_categories(self):
        """Events are properly categorized."""
        workflow_events = [e for e in WebhookEvent if e.value.startswith("workflow.")]
        step_events = [e for e in WebhookEvent if e.value.startswith("step.")]
        
        assert len(workflow_events) >= 4
        assert len(step_events) >= 3


class TestGlobalDispatcher:
    """Tests for global dispatcher functions."""
    
    def test_set_and_get_dispatcher(self):
        """Can set and get global dispatcher."""
        mock_dispatcher = MagicMock(spec=WebhookDispatcher)
        
        set_webhook_dispatcher(mock_dispatcher)
        result = get_webhook_dispatcher()
        
        assert result is mock_dispatcher
        
        # Cleanup
        set_webhook_dispatcher(None)
    
    @pytest.mark.asyncio
    async def test_emit_webhook_event(self):
        """Emits event through global dispatcher."""
        mock_dispatcher = MagicMock(spec=WebhookDispatcher)
        mock_dispatcher.dispatch_event = AsyncMock()
        
        set_webhook_dispatcher(mock_dispatcher)
        
        await emit_webhook_event(
            org_id="org-123",
            event=WebhookEvent.WORKFLOW_COMPLETED,
            workflow_id="wf-456",
            data={"result": "success"}
        )
        
        mock_dispatcher.dispatch_event.assert_called_once_with(
            "org-123",
            WebhookEvent.WORKFLOW_COMPLETED,
            "wf-456",
            {"result": "success"}
        )
        
        # Cleanup
        set_webhook_dispatcher(None)
    
    @pytest.mark.asyncio
    async def test_emit_webhook_event_no_dispatcher(self):
        """Handles missing dispatcher gracefully."""
        set_webhook_dispatcher(None)
        
        # Should not raise
        await emit_webhook_event(
            org_id="org-123",
            event=WebhookEvent.WORKFLOW_COMPLETED,
            workflow_id="wf-456",
            data={}
        )


class TestWebhookModels:
    """Tests for webhook Pydantic models."""
    
    def test_webhook_create_validation(self):
        """WebhookCreate validates input."""
        webhook = WebhookCreate(
            url="https://example.com/webhook",
            events=[WebhookEvent.WORKFLOW_COMPLETED, WebhookEvent.WORKFLOW_FAILED]
        )
        
        assert str(webhook.url) == "https://example.com/webhook"
        assert len(webhook.events) == 2
    
    def test_webhook_create_with_optional_fields(self):
        """WebhookCreate accepts optional fields."""
        webhook = WebhookCreate(
            url="https://example.com/webhook",
            events=[WebhookEvent.WORKFLOW_COMPLETED],
            secret="custom_secret",
            description="My webhook",
            headers={"Authorization": "Bearer token"},
            enabled=False
        )
        
        assert webhook.secret == "custom_secret"
        assert webhook.description == "My webhook"
        assert webhook.headers["Authorization"] == "Bearer token"
        assert webhook.enabled is False
    
    def test_webhook_update_partial(self):
        """WebhookUpdate allows partial updates."""
        update = WebhookUpdate(enabled=False)
        
        assert update.url is None
        assert update.events is None
        assert update.enabled is False
