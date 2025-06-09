# src/api/v1/routers/m365_auth.py
import os
import logging
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from datetime import datetime, timedelta, timezone

from src.auth_context.infrastructure.m365_oauth_client import M365OAuthClient
from src.auth_context.domain.user_m365_token import UserM365Token
from src.auth_context.infrastructure.user_m365_token_repository import MongoUserM365TokenRepository
from src.auth_context.application.encryption_utils import encrypt_token # decrypt_token might be needed for advanced status check
from src.auth_context.domain.user import User as DomainUser
from src.api.dependencies import get_current_active_user
from src.api.v1.schemas.auth_schemas import M365ConnectionStatus # Import the new Pydantic model

logger = logging.getLogger(__name__)
router = APIRouter()

STATE_SERIALIZER_SECRET_KEY = os.environ.get("STATE_SERIALIZER_SECRET_KEY", os.environ.get("JWT_SECRET_KEY"))
if not STATE_SERIALIZER_SECRET_KEY:
    logger.critical("CRITICAL: STATE_SERIALIZER_SECRET_KEY not set. Using insecure default.")
    STATE_SERIALIZER_SECRET_KEY = "insecure-default-state-key-pls-change"
state_serializer = URLSafeTimedSerializer(STATE_SERIALIZER_SECRET_KEY, salt="m365-oauth-state-cookie")

def get_m365_oauth_client():
    try:
        return M365OAuthClient()
    except ValueError as ve:
        logger.error(f"M365OAuthClient configuration error: {ve}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(ve))

def get_m365_token_repository():
    return MongoUserM365TokenRepository()

@router.get("/m365/authorize", summary="Initiate M365 OAuth", tags=["M365 Authentication"])
async def m365_authorize_redirect(
    request: Request,
    current_user: DomainUser = Depends(get_current_active_user),
    oauth_client: M365OAuthClient = Depends(get_m365_oauth_client)
):
    try:
        auth_flow_details_from_msal = oauth_client.msal_app.initiate_auth_code_flow(
            scopes=oauth_client.scopes, redirect_uri=oauth_client.redirect_uri
        )
        authorization_url = auth_flow_details_from_msal["auth_uri"]
        response = RedirectResponse(url=authorization_url, status_code=status.HTTP_302_FOUND)
        signed_flow_details_cookie_value = state_serializer.dumps(auth_flow_details_from_msal)
        response.set_cookie(
            key="m365_oauth_flow_details", value=signed_flow_details_cookie_value,
            max_age=600, httponly=True, samesite="Lax",
            # secure=True, # In production with HTTPS
        )
        logger.info(f"User '{current_user.username}' initiating M365 OAuth. State: {auth_flow_details_from_msal['state']}")
        return response
    except Exception as e:
        logger.error(f"Error initiating M365 auth for '{current_user.username}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to initiate M365 authorization.")

@router.get("/m365/callback", summary="Handle M365 OAuth Callback", tags=["M365 Authentication"])
async def m365_handle_callback(
    request: Request,
    current_user: DomainUser = Depends(get_current_active_user),
    oauth_client: M365OAuthClient = Depends(get_m365_oauth_client),
    token_repo: MongoUserM365TokenRepository = Depends(get_m365_token_repository)
):
    # (Previous callback logic from Step 5 of plan - assuming it's mostly correct)
    # Ensure frontend_redirect_url is correctly determined, e.g. from app state or config
    # For now, using hardcoded relative paths for dashboard redirects.
    dashboard_base_url = str(request.url_for('serve_dashboard_page')) # From frontend router

    try:
        signed_flow_details = request.cookies.get("m365_oauth_flow_details")
        if not signed_flow_details:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth flow details missing.")
        auth_code_flow_stashed = state_serializer.loads(signed_flow_details, max_age=610)

        auth_response_params = dict(request.query_params)
        token_response = oauth_client.acquire_token_by_auth_code_flow(auth_code_flow_stashed, auth_response_params)

        if not token_response or "access_token" not in token_response:
            err_desc = token_response.get("error_description", "Token acquisition failed.") if token_response else "Unknown token error."
            logger.error(f"M365 Callback: Token acquisition failed for '{current_user.username}'. Error: {err_desc}")
            return RedirectResponse(url=f"{dashboard_base_url}?error=M365 connection failed: {err_desc}", status_code=status.HTTP_302_FOUND)

        refresh_token = token_response.get("refresh_token")
        encrypted_rf = encrypt_token(refresh_token) if refresh_token else None
        if refresh_token and not encrypted_rf and os.environ.get("M365_TOKEN_ENCRYPTION_KEY"):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Token encryption failed.")

        expires_in = token_response.get("expires_in", 3600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

        token_obj = UserM365Token(
            user_id=current_user.id, encrypted_refresh_token=encrypted_rf,
            access_token_expires_at=expires_at, scopes=oauth_client.scopes,
            id_token_claims=token_response.get("id_token_claims", {})
        )
        if not token_repo.save(token_obj):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save M365 token.")

        response = RedirectResponse(url=f"{dashboard_base_url}?message=Microsoft 365 connected successfully.", status_code=status.HTTP_302_FOUND)
        response.delete_cookie("m365_oauth_flow_details")
        return response
    except (BadSignature, SignatureExpired) as e_state:
        logger.warning(f"M365 Callback: Invalid/expired state cookie for '{current_user.username}': {e_state}")
        return RedirectResponse(url=f"{dashboard_base_url}?error=Invalid or expired OAuth state. Please try again.", status_code=status.HTTP_302_FOUND)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in M365 callback for '{current_user.username}': {e}", exc_info=True)
        response = RedirectResponse(url=f"{dashboard_base_url}?error=Unexpected error during M365 connection.", status_code=status.HTTP_302_FOUND)
        response.delete_cookie("m365_oauth_flow_details") # Attempt to clear stale cookie
        return response

@router.post(
    "/m365/disconnect",
    summary="Disconnect Microsoft 365 Account",
    status_code=status.HTTP_200_OK,
    tags=["M365 Authentication"]
)
async def m365_disconnect(
    current_user: DomainUser = Depends(get_current_active_user),
    token_repo: MongoUserM365TokenRepository = Depends(get_m365_token_repository)
):
    logger.info(f"Attempting to disconnect M365 account for user_id: {current_user.id}")
    try:
        # Note: This only deletes the stored tokens from our application.
        # It does NOT revoke the app's consent from the user's Microsoft account.
        # User would have to do that manually via their Microsoft account settings.
        success = token_repo.delete_by_user_id(current_user.id)
        if success:
            logger.info(f"M365 tokens deleted for user_id: {current_user.id}")
            return {"message": "Microsoft 365 account disconnected successfully from this application."}
        else:
            logger.info(f"No M365 tokens found to delete for user_id: {current_user.id}")
            return {"message": "No Microsoft 365 account was connected or already disconnected."}
    except Exception as e:
        logger.error(f"Error disconnecting M365 account for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to disconnect M365 account due to a server error.")

@router.get(
    "/m365/status",
    response_model=M365ConnectionStatus,
    summary="Get Microsoft 365 Connection Status",
    tags=["M365 Authentication"]
)
async def get_m365_connection_status(
    current_user: DomainUser = Depends(get_current_active_user),
    token_repo: MongoUserM365TokenRepository = Depends(get_m365_token_repository)
    # oauth_client: M365OAuthClient = Depends(get_m365_oauth_client), # For active check
    # graph_client: GraphEmailClient = Depends(get_graph_client_dependency) # Hypothetical
):
    logger.info(f"Checking M365 connection status for user_id: {current_user.id}")
    user_m365_token = token_repo.get_by_user_id(current_user.id)

    if not user_m365_token or not user_m365_token.encrypted_refresh_token:
        logger.info(f"No M365 token record found for user_id: {current_user.id}")
        return M365ConnectionStatus(is_connected=False)

    account_email: Optional[str] = None
    if user_m365_token.id_token_claims:
        account_email = user_m365_token.id_token_claims.get('preferred_username') or \
                        user_m365_token.id_token_claims.get('email')

    logger.info(f"M365 token record found for user_id: {current_user.id}. Email from claims: {account_email}")

    # A more robust status check could try to use the refresh token to get a new access token,
    # and then make a simple Graph API call like /me. If successful, connection is truly live.
    # This simplified version relies on the presence of a stored (encrypted) refresh token
    # and any email information stored in the ID token claims.
    # If self.acquire_token_by_refresh_token in IngestionService fails, that's an indication
    # that the user might need to re-authenticate.

    return M365ConnectionStatus(
        is_connected=True,
        account_email=account_email
    )
```
