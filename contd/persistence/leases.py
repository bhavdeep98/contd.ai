"""
Lease manager with fencing tokens for distributed coordination.
"""
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Any, List
import logging

logger = logging.getLogger(__name__)


def utcnow():
    return datetime.utcnow()


@dataclass
class Lease:
    """
    Represents an active lease on a workflow.
    The fencing token is monotonically increasing and used to
    detect stale operations from previous lease holders.
    """
    workflow_id: str
    org_id: str
    owner_id: str
    token: int  # Fencing token - monotonically increasing
    expires_at: datetime
    acquired_at: datetime = None
    
    def is_expired(self) -> bool:
        return utcnow() > self.expires_at
    
    def time_remaining(self) -> timedelta:
        return self.expires_at - utcnow()


class LeaseManager:
    """
    Distributed lease manager with fencing tokens.
    
    Provides:
    - Exclusive workflow ownership via leases
    - Fencing tokens to detect stale operations
    - Automatic lease expiration
    - Heartbeat-based lease extension
    """
    
    LEASE_DURATION = timedelta(minutes=5)
    HEARTBEAT_INTERVAL = timedelta(seconds=30)
    
    def __init__(self, db: Any):
        self.db = db

    def acquire(self, workflow_id: str, owner_id: str, org_id: str = "default") -> Optional[Lease]:
        """
        Acquire exclusive lease on a workflow.
        
        Returns:
            Lease with fencing token if acquired, None if held by another owner.
        
        The fencing token is monotonically increasing - each new lease gets
        a higher token than all previous leases for this workflow.
        """
        now = utcnow()
        expires_at = now + self.LEASE_DURATION
        
        # Try to insert new lease (workflow not previously leased)
        try:
            token = self.db.execute("""
                INSERT INTO workflow_leases 
                (workflow_id, org_id, owner_id, acquired_at, lease_expires_at, fencing_token, heartbeat_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT (workflow_id) DO NOTHING
                RETURNING fencing_token
            """, workflow_id, org_id, owner_id, now, expires_at, now)
            
            if token:
                token = token[0] if isinstance(token, (list, tuple)) else token
                logger.info(f"Acquired new lease: workflow={workflow_id}, owner={owner_id}, token={token}")
                return Lease(workflow_id, org_id, owner_id, token, expires_at, now)
        except Exception as e:
            logger.debug(f"Insert failed (expected if lease exists): {e}")
        
        # Lease exists - try to acquire if expired
        result = self.db.execute("""
            UPDATE workflow_leases
            SET owner_id = ?,
                acquired_at = ?,
                lease_expires_at = ?,
                fencing_token = fencing_token + 1,
                heartbeat_at = ?
            WHERE workflow_id = ?
              AND org_id = ?
              AND lease_expires_at < ?
            RETURNING fencing_token
        """, owner_id, now, expires_at, now, workflow_id, org_id, now)
        
        if result:
            token = result[0] if isinstance(result, (list, tuple)) else result
            logger.info(f"Acquired expired lease: workflow={workflow_id}, owner={owner_id}, token={token}")
            return Lease(workflow_id, org_id, owner_id, token, expires_at, now)
        
        # Check if we already own it (re-entrant)
        existing = self.db.query("""
            SELECT fencing_token, lease_expires_at
            FROM workflow_leases
            WHERE workflow_id = ? AND org_id = ? AND owner_id = ?
        """, workflow_id, org_id, owner_id)
        
        if existing:
            row = existing[0] if isinstance(existing, list) else existing
            logger.info(f"Re-acquired own lease: workflow={workflow_id}, owner={owner_id}")
            return Lease(
                workflow_id, org_id, owner_id, 
                row['fencing_token'], 
                row['lease_expires_at'],
                now
            )
        
        logger.warning(f"Failed to acquire lease: workflow={workflow_id}, owner={owner_id}")
        return None
    
    def heartbeat(self, lease: Lease) -> bool:
        """
        Extend lease duration (idempotent).
        
        Returns:
            True if heartbeat succeeded, False if lease was lost.
        """
        now = utcnow()
        new_expires = now + self.LEASE_DURATION
        
        result = self.db.execute("""
            UPDATE workflow_leases
            SET heartbeat_at = ?,
                lease_expires_at = ?
            WHERE workflow_id = ?
              AND org_id = ?
              AND owner_id = ?
              AND fencing_token = ?
        """, now, new_expires, lease.workflow_id, lease.org_id, lease.owner_id, lease.token)
        
        if result and result > 0:
            lease.expires_at = new_expires
            return True
        
        logger.warning(f"Heartbeat failed - lease lost: workflow={lease.workflow_id}")
        return False
    
    def release(self, lease: Lease) -> bool:
        """
        Explicitly release a lease.
        
        Returns:
            True if released, False if already released or stolen.
        """
        result = self.db.execute("""
            DELETE FROM workflow_leases
            WHERE workflow_id = ?
              AND org_id = ?
              AND fencing_token = ?
        """, lease.workflow_id, lease.org_id, lease.token)
        
        released = result and result > 0
        if released:
            logger.info(f"Released lease: workflow={lease.workflow_id}, token={lease.token}")
        return released
    
    def validate_token(self, workflow_id: str, org_id: str, token: int) -> bool:
        """
        Validate that a fencing token is still current.
        
        Used to reject operations from stale lease holders.
        """
        result = self.db.query_val("""
            SELECT fencing_token
            FROM workflow_leases
            WHERE workflow_id = ? AND org_id = ?
        """, workflow_id, org_id)
        
        return result == token
    
    def get_current_lease(self, workflow_id: str, org_id: str = "default") -> Optional[Lease]:
        """Get the current lease holder info (if any)."""
        result = self.db.query("""
            SELECT owner_id, fencing_token, lease_expires_at, acquired_at
            FROM workflow_leases
            WHERE workflow_id = ? AND org_id = ?
        """, workflow_id, org_id)
        
        if not result:
            return None
        
        row = result[0] if isinstance(result, list) else result
        return Lease(
            workflow_id=workflow_id,
            org_id=org_id,
            owner_id=row['owner_id'],
            token=row['fencing_token'],
            expires_at=row['lease_expires_at'],
            acquired_at=row.get('acquired_at')
        )
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired leases.
        Returns count of cleaned up leases.
        """
        result = self.db.execute("""
            DELETE FROM workflow_leases
            WHERE lease_expires_at < ?
        """, utcnow())
        
        count = result if isinstance(result, int) else 0
        if count > 0:
            logger.info(f"Cleaned up {count} expired leases")
        return count
    
    def list_active_leases(self, org_id: str = None) -> List[Lease]:
        """List all active (non-expired) leases."""
        if org_id:
            rows = self.db.query("""
                SELECT workflow_id, org_id, owner_id, fencing_token, lease_expires_at, acquired_at
                FROM workflow_leases
                WHERE org_id = ? AND lease_expires_at > ?
            """, org_id, utcnow())
        else:
            rows = self.db.query("""
                SELECT workflow_id, org_id, owner_id, fencing_token, lease_expires_at, acquired_at
                FROM workflow_leases
                WHERE lease_expires_at > ?
            """, utcnow())
        
        return [
            Lease(
                workflow_id=r['workflow_id'],
                org_id=r['org_id'],
                owner_id=r['owner_id'],
                token=r['fencing_token'],
                expires_at=r['lease_expires_at'],
                acquired_at=r.get('acquired_at')
            )
            for r in (rows or [])
        ]


class LeaseError(Exception):
    """Base exception for lease operations."""
    pass


class LeaseNotHeldError(LeaseError):
    """Raised when an operation requires a lease that isn't held."""
    pass


class StaleLeaseError(LeaseError):
    """Raised when a fencing token is stale."""
    pass
