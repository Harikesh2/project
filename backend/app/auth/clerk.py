import asyncio
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import httpx
from typing import Optional, Dict, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()


class ClerkAuth:
    def __init__(self):
        self.secret_key = settings.clerk_secret_key
        # Use settings for dynamic JWKS URL, fallback to default for safety
        self.jwks_url = settings.clerk_jwks_url or "https://api.clerk.dev/v1/jwks"
        self.issuer = settings.clerk_issuer
        self._jwks_cache: Optional[Dict[str, Any]] = None
        self._lock = asyncio.Lock()
    
    async def get_jwks(self) -> Dict[str, Any]:
        """Get JWKS from Clerk API with caching"""
        if self._jwks_cache is None:
            async with self._lock:
                # Double-check inside the lock to avoid multiple concurrent fetches
                if self._jwks_cache is None:
                    logger.info(f"Fetching JWKS from {self.jwks_url}")
                    # Added an explicit timeout as the default 5s sometimes timeouts
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(self.jwks_url)
                        response.raise_for_status()
                        self._jwks_cache = response.json()
        return self._jwks_cache
    
    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify Clerk JWT token and return user claims"""
        try:
            # Handle local demo token for development
            if settings.debug and token == "demo_token_123":
                return {
                    "sub": "demo_user_123",
                    "email": "demo@example.com",
                    "username": "demo_user"
                }

            # 1. Get the Key ID (kid) from the token header
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get('kid')
            logger.info(f"Token kid: {kid}, alg: {unverified_header.get('alg')}")
            
            if not kid:
                raise JWTError("Missing 'kid' in token header")

            # 2. Get the public keys from Clerk
            jwks = await self.get_jwks()
            logger.info(f"JWKS has {len(jwks.get('keys', []))} keys")
            
            # 3. Find the signing key that matches the kid
            key_data = next((k for k in jwks['keys'] if k['kid'] == kid), None)
            if not key_data:
                available_kids = [k['kid'] for k in jwks.get('keys', [])]
                logger.error(f"kid '{kid}' not in available keys: {available_kids}")
                raise JWTError(f"Unable to find a signing key that matches 'kid': {kid}")
            
            # 4. Decode and verify the token using the JWK
            from jose.backends import RSAKey
            rsa_key = RSAKey(key_data, algorithm="RS256")
            
            payload = jwt.decode(
                token,
                rsa_key.public_key().to_dict(),
                algorithms=["RS256"],
                issuer=self.issuer,
                options={"verify_aud": False}
            )
            logger.info(f"Token verified successfully for user: {payload.get('sub')}")
            return payload
            
        except JWTError as e:
            logger.error(f"JWT verification failed: {e}")
            # In debug mode, try to extract claims without verification as last resort
            if settings.debug:
                try:
                    logger.warning("DEBUG mode: extracting unverified claims as fallback")
                    payload = jwt.get_unverified_claims(token)
                    if payload.get("sub"):
                        return payload
                except Exception:
                    pass
            raise HTTPException(
                status_code=401,
                detail=f"Invalid authentication token: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during token verification: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Internal server error during authentication"
            )
    
    def _get_signing_key(self, token: str, jwks: Dict[str, Any]) -> str:
        """Get the signing key from JWKS"""
        pass


clerk_auth = ClerkAuth()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    user_claims = await clerk_auth.verify_token(token)
    
    # Extract user ID from Clerk claims
    user_id = user_claims.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid token: missing user ID"
        )
    
    return {
        "user_id": user_id,
        "email": user_claims.get("email"),
        "username": user_claims.get("username"),
        "claims": user_claims
    }