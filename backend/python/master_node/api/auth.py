"""
Authentication endpoints for the GTO Poker Solver API.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from ..core.security import auth_handler, get_current_user, require_permission
from ..db.database import get_db_session
from ..db.models import User, APIKey

router = APIRouter()


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    permissions: List[str] = []


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class APIKeyCreate(BaseModel):
    name: str
    permissions: List[str] = []


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key: str
    permissions: List[str]
    created_at: str


@router.post("/register", response_model=dict)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(require_permission("admin")),
):
    """Register a new user (admin only)."""
    # Check if user already exists
    existing_user = await db.execute(
        select(User).filter(User.username == user_data.username)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Create new user
    hashed_password = auth_handler.get_password_hash(user_data.password)
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        permissions=user_data.permissions,
        is_active=True,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {"message": "User created successfully", "user_id": str(user.id)}


@router.post("/login", response_model=Token)
async def login(
    user_credentials: UserLogin, db: AsyncSession = Depends(get_db_session)
):
    """Authenticate user and return JWT token."""
    # Find user
    result = await db.execute(
        select(User).filter(User.username == user_credentials.username)
    )
    user = result.scalar_one_or_none()

    if not user or not auth_handler.verify_password(
        user_credentials.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is disabled"
        )

    # Create access token
    access_token = auth_handler.encode_token(str(user.id), user.permissions)

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    api_key_data: APIKeyCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(require_permission("admin")),
):
    """Create a new API key (admin only)."""
    import secrets
    import string

    # Generate API key
    alphabet = string.ascii_letters + string.digits
    key = "".join(secrets.choice(alphabet) for _ in range(32))

    api_key = APIKey(
        name=api_key_data.name,
        key=f"gto_{key}",
        permissions=api_key_data.permissions,
        created_by=current_user["sub"],
    )

    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return APIKeyResponse(
        id=str(api_key.id),
        name=api_key.name,
        key=api_key.key,
        permissions=api_key.permissions,
        created_at=api_key.created_at.isoformat(),
    )


@router.get("/api-keys")
async def list_api_keys(
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(require_permission("admin")),
):
    """List all API keys (admin only)."""
    result = await db.execute(select(APIKey))
    api_keys = result.scalars().all()

    return {
        "api_keys": [
            {
                "id": str(key.id),
                "name": key.name,
                "permissions": key.permissions,
                "created_at": key.created_at.isoformat(),
                "is_active": key.is_active,
            }
            for key in api_keys
        ]
    }


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(require_permission("admin")),
):
    """Revoke an API key (admin only)."""
    result = await db.execute(select(APIKey).filter(APIKey.id == key_id))
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )

    api_key.is_active = False
    await db.commit()

    return {"message": "API key revoked"}


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information."""
    return {"user_id": current_user["sub"], "permissions": current_user["permissions"]}
