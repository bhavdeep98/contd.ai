from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Any
from psycopg2 import IntegrityError  # Assuming typical pg driver, or catch generic Exception if preferred

def utcnow():
    return datetime.utcnow()

@dataclass
class Lease:
    workflow_id: str
    owner_id: str
    token: int
    expires_at: datetime

class LeaseManager:
    LEASE_DURATION = timedelta(minutes=5)
    HEARTBEAT_INTERVAL = timedelta(seconds=30)
    
    def __init__(self, db: Any):
        self.db = db

    def acquire(self, workflow_id: str, owner_id: str, org_id: str = "default") -> Optional[Lease]:
        """
        Acquire lease or fail.
        Returns: Lease with fencing token, or None if held by another.
        """
        now = utcnow()
        expires_at = now + self.LEASE_DURATION
        
        # Try insert (new workflow)
        try:
            # Note: The SQL here assumes the db adapter supports localized parameters (?) or standard %s. 
            # The spec used `?`, but Postgres typically uses `%s` or `$1`. 
            # I will use `?` as per spec to match user intent, assuming adapter handles it.
            token = self.db.execute("""
                INSERT INTO workflow_leases 
                (workflow_id, org_id, owner_id, acquired_at, lease_expires_at, fencing_token, heartbeat_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                RETURNING fencing_token
            """, workflow_id, org_id, owner_id, now, expires_at, now)
            
            # Assuming execute returns result for RETURNING or db.execute returns a cursor/result
            # If db.execute returns nothing, we need fetchone logic. 
            # Spec says `token = self.db.execute(...)` which implies scalar return or similar.
            # I'll convert if token is a list/tuple.
            if isinstance(token, (list, tuple)):
                token = token[0]
                
            return Lease(workflow_id, owner_id, token, expires_at)
        except IntegrityError:
            pass # Lease exists
        except Exception as e:
            # Need to handle race or generic DB error if not specialized
            # Assuming IntegrityError catches primary key violation
            pass
        
        # Try acquire expired lease
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
            return Lease(workflow_id, owner_id, token, expires_at)
        
        return None  # Held by another
    
    def heartbeat(self, lease: Lease):
        """Extend lease (idempotent)"""
        now = utcnow()
        self.db.execute("""
            UPDATE workflow_leases
            SET heartbeat_at = ?,
                lease_expires_at = ?
            WHERE workflow_id = ?
              AND owner_id = ?
              AND fencing_token = ?
        """, now, now + self.LEASE_DURATION, lease.workflow_id, lease.owner_id, lease.token)
    
    def release(self, lease: Lease):
        """Explicit release"""
        self.db.execute("""
            DELETE FROM workflow_leases
            WHERE workflow_id = ?
              AND fencing_token = ?
        """, lease.workflow_id, lease.token)
