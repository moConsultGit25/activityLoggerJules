# src/api/v1/routers/google_auth.py
import os
import logging
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from datetime import datetime, timezone, timedelta
import httpx # For Google token revocation

# Google Auth specific imports
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_auth_transport_requests

from src.auth_context.infrastructure.google_oauth_client import GoogleOAuthClient
from src.auth_context.domain.user_google_token import UserGoogleToken
from src.auth_context.infrastructure.user_google_token_repository import MongoUserGoogleTokenRepository
from src.auth_context.application.encryption_utils import encrypt_token, decrypt_token # Added decrypt_token
from src.auth_context.domain.user import User as DomainUser
from src.api.dependencies import get_current_active_user
from src.api.v1.schemas.auth_schemas import GoogleConnectionStatus # Import the Pydantic model

logger = logging.getLogger(__name__)
router = APIRouter()

_state_key = os.environ.get("STATE_SERIALIZER_SECRET_KEY", os.environ.get("JWT_SECRET_KEY"))
if not _state_key:
    _state_key = "default_unsafe_google_state_secret_key_32_bytes_pls_change" # Fallback for safety
    logger.critical("CRITICAL: STATE_SERIALIZER_SECRET_KEY not set for Google OAuth state. THIS IS INSECURE.")
state_serializer = URLSafeTimedSerializer(_state_key, salt="google-oauth-state-csrf")

def get_google_oauth_client_dependency() -> GoogleOAuthClient:
    try: return GoogleOAuthClient()
    except ValueError as ve:
        logger.error(f"GoogleOAuthClient config error: {ve}");
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Google auth not configured: {ve}")

def get_google_token_repository_dependency() -> MongoUserGoogleTokenRepository:
    return MongoUserGoogleTokenRepository()

@router.get("/google/authorize", summary="Initiate Google OAuth", tags=["Google Authentication"])
async def google_authorize_user_redirect(
    request: Request, current_user: DomainUser = Depends(get_current_active_user),
    google_client: GoogleOAuthClient = Depends(get_google_oauth_client_dependency)
):
    try:
        csrf_state_payload = os.urandom(24).hex()
        signed_csrf_cookie_val = state_serializer.dumps(csrf_state_payload)
        auth_url, _ = google_client.get_authorization_request_url(state=csrf_state_payload)
        response = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
        response.set_cookie(key="google_oauth_state_csrf", value=signed_csrf_cookie_val, max_age=600, httponly=True, samesite="Lax")
        logger.info(f"User '{current_user.username}' initiating Google OAuth. CSRF state: {csrf_state_payload}")
        return response
    except Exception as e:
        logger.error(f"Error initiating Google OAuth for '{current_user.username}': {e}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to initiate Google authorization.")

@router.get("/google/callback", summary="Handle Google OAuth Callback", tags=["Google Authentication"])
async def google_handle_callback(
    request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None,
    current_user: DomainUser = Depends(get_current_active_user),
    google_client: GoogleOAuthClient = Depends(get_google_oauth_client_dependency),
    token_repo: MongoUserGoogleTokenRepository = Depends(get_google_token_repository_dependency)
):
    dashboard_url = str(request.url_for('serve_dashboard_page'))
    response_params = {"error": "An unexpected error occurred during Google connection."} # Default error

    try:
        if error: raise HTTPException(status.HTTP_400_BAD_REQUEST, f"GoogleAuthError: {request.query_params.get('error_description', error)}")
        if not code or not state: raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid callback: code or state missing.")

        signed_csrf_cookie = request.cookies.get("google_oauth_state_csrf")
        if not signed_csrf_cookie: raise HTTPException(status.HTTP_400_BAD_REQUEST, "CSRF state cookie missing.")

        original_csrf_payload = state_serializer.loads(signed_csrf_cookie, max_age=610)
        if original_csrf_payload != state: raise HTTPException(status.HTTP_400_BAD_REQUEST, "CSRF state mismatch.")

        token_response = google_client.fetch_tokens_by_auth_code(str(request.url))
        if not token_response or "access_token" not in token_response:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Failed to acquire Google token from code.")

        rt = token_response.get("refresh_token")
        enc_rt = encrypt_token(rt) if rt else None
        if rt and not enc_rt and os.environ.get("GOOGLE_TOKEN_ENCRYPTION_KEY"):
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to secure Google token (encryption).")

        exp_at_iso = token_response.get("expires_at_iso")
        exp_at_dt = datetime.fromisoformat(exp_at_iso.replace('Z', '+00:00')) if exp_at_iso else None

        id_claims = None
        raw_id_token = token_response.get("id_token")
        if raw_id_token:
            try:
                id_info = google_id_token.verify_oauth2_token(raw_id_token, google_auth_transport_requests.Request(), google_client.client_id)
                id_claims = {"email": id_info.get("email"), "name": id_info.get("name"), "sub": id_info.get("sub")}
            except Exception as id_exc: logger.warning(f"Failed to verify/decode Google ID token for {current_user.id}: {id_exc}")

        token_obj = UserGoogleToken(user_id=current_user.id, encrypted_refresh_token=enc_rt,
                                 access_token_expires_at=exp_at_dt, scopes=token_response.get("scopes"),
                                 id_token_claims=id_claims)
        if not token_repo.save(token_obj):
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to save Google token.")

        logger.info(f"Google account connected for user '{current_user.username}'.")
        response_params = {"message": "Google account connected successfully."}
    except (BadSignature, SignatureExpired) as e_state:
        logger.warning(f"Google callback: Invalid/expired state cookie for '{current_user.username}': {e_state}")
        response_params["error"] = "Invalid or expired session state. Please try authorizing again."
    except HTTPException as http_exc: # Specific HTTP errors raised above
        response_params["error"] = http_exc.detail
    except Exception as e:
        logger.error(f"Error in Google callback for '{current_user.username}': {e}", exc_info=True)
        # response_params["error"] is already set to default

    final_redirect_url = f"{dashboard_url}?{ '&'.join([f'{k}={v}' for k,v in response_params.items() if v]) }"
    response = RedirectResponse(url=final_redirect_url, status_code=status.HTTP_302_FOUND)
    response.delete_cookie("google_oauth_state_csrf")
    return response

@router.post("/google/disconnect", summary="Disconnect Google Gmail Account", tags=["Google Authentication"])
async def google_disconnect(
    current_user: DomainUser = Depends(get_current_active_user),
    token_repo: MongoUserGoogleTokenRepository = Depends(get_google_token_repository_dependency)
):
    logger.info(f"Attempting to disconnect Google account for user_id: {current_user.id}")
    try:
        user_google_token = token_repo.get_by_user_id(current_user.id)
        if user_google_token and user_google_token.encrypted_refresh_token:
            decrypted_refresh_token = decrypt_token(user_google_token.encrypted_refresh_token)
            if decrypted_refresh_token:
                async with httpx.AsyncClient() as client:
                    revoke_url = "https://oauth2.googleapis.com/revoke"
                    resp = await client.post(revoke_url, params={'token': decrypted_refresh_token})
                    if resp.status_code == 200: logger.info(f"Revoked Google refresh token for user {current_user.id}.")
                    else: logger.warning(f"Failed to revoke Google token for user {current_user.id}. Status: {resp.status_code}, Resp: {resp.text}")

        deleted = token_repo.delete_by_user_id(current_user.id)
        if deleted: return {"message": "Google Gmail account disconnected successfully."}
        return {"message": "No Google Gmail account was connected or already disconnected."}
    except Exception as e:
        logger.error(f"Error disconnecting Google for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to disconnect Google Gmail account.")

@router.get("/google/status", response_model=GoogleConnectionStatus, summary="Get Google Gmail Connection Status", tags=["Google Authentication"])
async def get_google_connection_status(
    current_user: DomainUser = Depends(get_current_active_user),
    token_repo: MongoUserGoogleTokenRepository = Depends(get_google_token_repository_dependency)
):
    user_token = token_repo.get_by_user_id(current_user.id)
    if not user_token or not user_token.encrypted_refresh_token:
        return GoogleConnectionStatus(is_connected=False)

    email = user_token.id_token_claims.get("email") if user_token.id_token_claims else None
    # More robust status check could attempt token refresh here. For now, presence implies connected.
    return GoogleConnectionStatus(is_connected=True, account_email=email)

```
