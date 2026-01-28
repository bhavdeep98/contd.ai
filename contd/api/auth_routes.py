from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from contd.models.auth import (
    UserCreate,
    User,
    Token,
    OrganizationCreate,
    Organization,
    ApiKeyCreate,
)
from contd.persistence.auth_store import AuthStore
from contd.api.dependencies import (
    get_auth_store,
    get_current_user,
    get_auth_context,
    AuthContext,
)
from contd.core.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    generate_api_key,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/signup", response_model=User)
async def signup(user: UserCreate, store: AuthStore = Depends(get_auth_store)):
    db_user = store.get_user_by_email(user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    new_user = store.create_user(user.email, hashed_password, user.full_name)
    return new_user


@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    store: AuthStore = Depends(get_auth_store),
):
    user = store.get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    access_token = create_access_token(data={"sub": str(user.user_id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/organizations", response_model=Organization)
async def create_org(
    org: OrganizationCreate,
    user: User = Depends(get_current_user),
    store: AuthStore = Depends(get_auth_store),
):
    new_org = store.create_organization(org.name, str(user.user_id))
    return new_org


@router.post("/apikeys")
async def create_api_key_endpoint(
    key_in: ApiKeyCreate,
    ctx: AuthContext = Depends(get_auth_context),
    store: AuthStore = Depends(get_auth_store),
):
    if ctx.is_service:
        raise HTTPException(
            status_code=403, detail="API Keys cannot create new API Keys"
        )

    raw_key, key_hash = generate_api_key()

    # Prefix is usually first few chars
    raw_key.split("_")[0] + "_" + raw_key.split("_")[1] + "_"  # e.g. sk_live_
    # But generate_api_key returns prefix+random.
    # We want to store prefix for display. My generate logic: prefix="sk_live_" -> "sk_live_ABCD..."

    api_key = store.create_api_key(
        org_id=ctx.org_id,
        name=key_in.name,
        key_prefix="sk_live",
        key_hash=key_hash,
        scopes=key_in.scopes,
        user_id=ctx.user_id,
    )

    resp = api_key.dict()
    resp["secret_key"] = raw_key
    return resp
