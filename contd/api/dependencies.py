from fastapi import Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from jose import JWTError
import hashlib
from typing import Optional, Union

from contd.core.auth import decode_access_token
from contd.persistence.auth_store import AuthStore
from contd.core.engine import ExecutionEngine
from contd.models.auth import UserInDB, Organization, ApiKey

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/auth/token", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_db():
    engine = ExecutionEngine.get_instance()
    return engine.db

async def get_auth_store(db = Depends(get_db)):
    return AuthStore(db)

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    store: AuthStore = Depends(get_auth_store)
) -> Optional[UserInDB]:
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = store.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def get_api_key(
    key: str = Depends(api_key_header),
    store: AuthStore = Depends(get_auth_store)
) -> Optional[ApiKey]:
    if not key:
        return None
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    return store.get_api_key_by_hash(key_hash)

class AuthContext:
    def __init__(self, org_id: str, user_id: Optional[str] = None, is_service: bool = False):
        self.org_id = org_id
        self.user_id = user_id
        self.is_service = is_service

async def get_auth_context(
    request: Request,
    user: Optional[UserInDB] = Depends(get_current_user),
    api_key: Optional[ApiKey] = Depends(get_api_key),
    store: AuthStore = Depends(get_auth_store)
) -> AuthContext:
    # Priority 1: API Key
    if api_key:
        return AuthContext(str(api_key.org_id), str(api_key.user_id) if api_key.user_id else None, is_service=True)
    
    # Priority 2: User Session
    if user:
        org_id = request.headers.get("X-Organization-Id")
        if not org_id:
            # Infer org
            orgs = store.get_user_organizations(user.user_id)
            if len(orgs) == 1:
                return AuthContext(str(orgs[0][0].org_id), str(user.user_id))
            elif len(orgs) == 0:
                raise HTTPException(status_code=403, detail="User has no organization")
            else:
                 raise HTTPException(status_code=400, detail="X-Organization-Id header required")
        
        # Verify
        orgs = store.get_user_organizations(user.user_id)
        if not any(str(o[0].org_id) == org_id for o in orgs):
             raise HTTPException(status_code=403, detail="Not a member of this organization")
             
        return AuthContext(org_id, str(user.user_id))

    raise HTTPException(status_code=401, detail="Not authenticated")
