"""
Security utilities for the GTO Poker Solver.
Implements JWT authentication, API key management, and rate limiting.
"""

import time
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis
import sqlalchemy
from .config import settings

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Rate limiting storage
if settings.REDIS_URL:
    redis_client = redis.from_url(settings.REDIS_URL)
else:
    redis_client = None

class AuthHandler:
    """Handles JWT token creation and validation."""
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def encode_token(self, user_id: str, permissions: list = None) -> str:
        """Create a JWT token."""
        payload = {
            'exp': datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            'iat': datetime.utcnow(),
            'sub': user_id,
            'permissions': permissions or []
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Token has expired'
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Invalid token'
            )

auth_handler = AuthHandler()
security = HTTPBearer()

class RateLimiter:
    """Rate limiting middleware."""
    
    def __init__(self, calls: int, period: int):
        self.calls = calls
        self.period = period
    
    def __call__(self, request: Request):
        if not redis_client:
            return  # Skip rate limiting if Redis is not available
            
        client_ip = request.client.host
        key = f"rate_limit:{client_ip}"
        
        try:
            current = redis_client.get(key)
            if current is None:
                redis_client.setex(key, self.period, 1)
            else:
                current = int(current)
                if current >= self.calls:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded. Max {self.calls} requests per {self.period} seconds.",
                        headers={
                            "X-RateLimit-Limit": str(self.calls),
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Reset": str(int(time.time()) + self.period)
                        }
                    )
                redis_client.incr(key)
                
                # Add rate limit headers to successful requests
                remaining = max(0, self.calls - current - 1)
                request.state.rate_limit_headers = {
                    "X-RateLimit-Limit": str(self.calls),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(int(time.time()) + self.period)
                }
        except redis.RedisError:
            # If Redis is down, allow the request to proceed
            pass

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Extract and validate the current user from JWT token."""
    token = credentials.credentials
    payload = auth_handler.decode_token(token)
    return payload

def require_permission(permission: str):
    """Decorator to require specific permission."""
    def permission_checker(current_user: Dict[str, Any] = Depends(get_current_user)):
        user_permissions = current_user.get('permissions', [])
        if permission not in user_permissions and 'admin' not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f'Insufficient permissions. Required: {permission}'
            )
        return current_user
    return permission_checker

class APIKeyAuth:
    """API Key authentication for service-to-service communication."""
    
    def __init__(self):
        self.valid_keys = settings.API_KEYS.split(',') if hasattr(settings, 'API_KEYS') else []
    
    def __call__(self, request: Request):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='API key required'
            )
        
        if api_key not in self.valid_keys:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Invalid API key'
            )
        
        return api_key

# Rate limiting instances for different endpoints
rate_limiter_general = RateLimiter(calls=100, period=60)  # 100 requests per minute
rate_limiter_simulation = RateLimiter(calls=10, period=60)  # 10 simulation requests per minute
rate_limiter_status = RateLimiter(calls=200, period=60)  # 200 status requests per minute

# Enhanced API Key validation with database lookup
async def validate_api_key(request: Request):
    """Validate API key from database."""
    from ..db.database import get_db_session
    
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='API key required'
        )
    
    try:
        from ..db.models import APIKey
        from sqlalchemy import select
        
        async with get_db_session() as db:
            result = await db.execute(
                select(APIKey).filter(APIKey.key == api_key, APIKey.is_active == True)
            )
            api_key_obj = result.scalar_one_or_none()
            
            if not api_key_obj:
                await audit_logger.log_security_event(
                    "invalid_api_key_attempt", 
                    details={"api_key_prefix": api_key[:8] + "..."}, 
                    request=request
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail='Invalid or inactive API key'
                )
            
            # Update last used timestamp
            api_key_obj.last_used = datetime.utcnow()
            await db.commit()
            
            await audit_logger.log_security_event(
                "api_key_access", 
                api_key_id=str(api_key_obj.id),
                details={"name": api_key_obj.name}, 
                request=request
            )
            
            return {
                'api_key_id': str(api_key_obj.id),
                'permissions': api_key_obj.permissions,
                'name': api_key_obj.name
            }
    except ImportError:
        # Fallback to simple validation if database models aren't available
        logger.warning("Database models not available, using simple API key validation")
        api_key_auth = APIKeyAuth()
        return api_key_auth(request)

# Input validation and sanitization
class SecurityValidator:
    """Security validation utilities."""
    
    @staticmethod
    def validate_simulation_name(name: str) -> str:
        """Validate and sanitize simulation name."""
        if not name or len(name.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Simulation name cannot be empty"
            )
        
        # Remove potentially dangerous characters
        import re
        sanitized = re.sub(r'[<>"\'/\\&]', '', name.strip())
        
        if len(sanitized) > 255:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Simulation name too long (max 255 characters)"
            )
        
        return sanitized
    
    @staticmethod
    def validate_json_size(data: dict, max_size_mb: int = 10) -> dict:
        """Validate JSON payload size."""
        import json
        import sys
        
        size_bytes = sys.getsizeof(json.dumps(data).encode('utf-8'))
        size_mb = size_bytes / (1024 * 1024)
        
        if size_mb > max_size_mb:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Request payload too large. Max size: {max_size_mb}MB"
            )
        
        return data

# Security middleware for adding headers
class SecurityHeadersMiddleware:
    """Add security headers to responses."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            response = await self.app(scope, receive, send)
            
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = dict(message.get("headers", []))
                    
                    # Add security headers
                    security_headers = {
                        b"x-content-type-options": b"nosniff",
                        b"x-frame-options": b"DENY",
                        b"x-xss-protection": b"1; mode=block",
                        b"strict-transport-security": b"max-age=31536000; includeSubDomains",
                        b"content-security-policy": b"default-src 'self'",
                        b"referrer-policy": b"strict-origin-when-cross-origin",
                    }
                    
                    # Add rate limit headers if present
                    if hasattr(scope.get("state", {}), "rate_limit_headers"):
                        rate_headers = scope["state"].rate_limit_headers
                        for key, value in rate_headers.items():
                            security_headers[key.lower().encode()] = value.encode()
                    
                    headers.update(security_headers)
                    message["headers"] = list(headers.items())
                
                await send(message)
            
            return await send_wrapper
        
        return await self.app(scope, receive, send)

# Audit logging
class AuditLogger:
    """Security audit logging."""
    
    @staticmethod
    async def log_security_event(event_type: str, user_id: str = None, 
                                api_key_id: str = None, details: dict = None,
                                request: Request = None):
        """Log security-related events."""
        import json
        from datetime import datetime
        
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "api_key_id": api_key_id,
            "client_ip": request.client.host if request else None,
            "user_agent": request.headers.get("user-agent") if request else None,
            "details": details or {}
        }
        
        # Log to application logger with structured format
        logger.info(f"SECURITY_AUDIT: {json.dumps(audit_entry)}")
        
        # In production, you might also send to a dedicated security log system
        # or SIEM (Security Information and Event Management) system

audit_logger = AuditLogger()
security_validator = SecurityValidator()
