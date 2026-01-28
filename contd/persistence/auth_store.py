from uuid import uuid4
from datetime import datetime
from typing import Optional, List, Tuple
from contd.models.auth import UserInDB, Organization, ApiKey, UserRole


class AuthStore:
    def __init__(self, db):
        self.db = db

    def create_user(
        self, email: str, password_hash: str, full_name: str = None
    ) -> UserInDB:
        user_id = uuid4()
        now = datetime.utcnow()
        self.db.execute(
            "INSERT INTO users (user_id, email, password_hash, full_name, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            str(user_id),
            email,
            password_hash,
            full_name,
            now,
            now,
        )
        return UserInDB(
            user_id=user_id,
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            created_at=now,
            updated_at=now,
        )

    def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        rows = self.db.query("SELECT * FROM users WHERE email = ?", email)
        if not rows:
            return None
        return UserInDB(**rows[0])

    def get_user_by_id(self, user_id: str) -> Optional[UserInDB]:
        rows = self.db.query("SELECT * FROM users WHERE user_id = ?", str(user_id))
        if not rows:
            return None
        return UserInDB(**rows[0])

    def create_organization(self, name: str, owner_id: str) -> Organization:
        org_id = uuid4()
        now = datetime.utcnow()
        # Transaction ideally
        self.db.execute(
            "INSERT INTO organizations (org_id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            str(org_id),
            name,
            now,
            now,
        )
        self.add_org_member(str(org_id), owner_id, UserRole.OWNER)
        return Organization(org_id=org_id, name=name, created_at=now, updated_at=now)

    def add_org_member(self, org_id: str, user_id: str, role: UserRole):
        self.db.execute(
            "INSERT INTO organization_members (org_id, user_id, role) VALUES (?, ?, ?)",
            str(org_id),
            str(user_id),
            role.value,
        )

    def get_user_organizations(self, user_id: str) -> List[Tuple[Organization, str]]:
        """Returns list of (Organization, role)"""
        sql = """
            SELECT o.*, m.role 
            FROM organizations o
            JOIN organization_members m ON o.org_id = m.org_id
            WHERE m.user_id = ?
        """
        rows = self.db.query(sql, str(user_id))
        results = []
        for row in rows:
            role = row.pop("role")
            results.append((Organization(**row), role))
        return results

    def create_api_key(
        self,
        org_id: str,
        name: str,
        key_prefix: str,
        key_hash: str,
        scopes: List[str],
        user_id: str = None,
    ) -> ApiKey:
        key_id = uuid4()
        now = datetime.utcnow()
        self.db.execute(
            """INSERT INTO api_keys (key_id, key_prefix, key_hash, org_id, user_id, name, scopes, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            str(key_id),
            key_prefix,
            key_hash,
            str(org_id),
            str(user_id) if user_id else None,
            name,
            scopes,
            now,
        )
        return ApiKey(
            key_id=key_id,
            key_prefix=key_prefix,
            org_id=org_id,
            user_id=user_id,
            name=name,
            scopes=scopes,
            created_at=now,
        )

    def get_api_key_by_hash(self, key_hash: str) -> Optional[ApiKey]:
        # In reality, we might search by prefix first to narrow down, then check hash.
        # But here we assume we can query by hash (indexed).
        rows = self.db.query("SELECT * FROM api_keys WHERE key_hash = ?", key_hash)
        if not rows:
            return None
        return ApiKey(**rows[0])
