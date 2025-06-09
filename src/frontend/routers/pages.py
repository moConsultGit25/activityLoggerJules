# src/frontend/routers/pages.py
from fastapi import APIRouter, Request, Depends, Form, HTTPException, status, UploadFile, File, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import httpx
from pathlib import Path
from typing import Optional, Annotated, Dict, Any

BASE_DIR_FE = Path(__file__).resolve().parent.parent
TEMPLATES_DIR_FE = BASE_DIR_FE / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR_FE)

router = APIRouter(
    tags=["Frontend Pages"],
    include_in_schema=False
)

# --- Helper to get auth token from cookie ---
def get_auth_token_from_cookie(request: Request) -> Optional[str]:
    token_cookie = request.cookies.get("access_token")
    if token_cookie and token_cookie.startswith("Bearer "):
        return token_cookie.split(" ")[1]
    return token_cookie

# --- Root / Home Page ---
@router.get("/", response_class=HTMLResponse, name="serve_home_page")
async def serve_home_page(request: Request, message: Optional[str] = None, error: Optional[str] = None):
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "title": "Home", "message": message, "error_message": error}
    )

# --- Login Routes ---
@router.get("/login", response_class=HTMLResponse, name="serve_login_page")
async def serve_login_page(request: Request, message: Optional[str] = None, error_message: Optional[str] = None):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "title": "Login", "success_message": message, "error_message": error_message}
    )

@router.post("/login", response_class=HTMLResponse, name="handle_login_form")
async def handle_login_form(request: Request, username: str = Form(...), password: str = Form(...)):
    api_login_url = str(request.url_for('login_for_access_token')) # API route name
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(api_login_url, data={"username": username, "password": password})
            response.raise_for_status()
            token_data = response.json()
            access_token = token_data.get("access_token")

            redirect_url = request.url_for('serve_dashboard_page')
            redirect_response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
            redirect_response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True, samesite="lax")
            return redirect_response
        except httpx.HTTPStatusError as e:
            error_detail = e.response.json().get("detail", "Invalid username or password.")
            return templates.TemplateResponse("login.html", {"request": request, "title": "Login", "error_message": error_detail, "username": username})
        except httpx.RequestError:
            return templates.TemplateResponse("login.html", {"request": request, "title": "Login", "error_message": "Login service unavailable.", "username": username})

# --- Registration Routes ---
@router.get("/register", response_class=HTMLResponse, name="serve_register_page")
async def serve_register_page(request: Request, error_message: Optional[str] = None, username_value: Optional[str] = None):
    return templates.TemplateResponse("register.html", {"request": request, "title": "Register", "error_message": error_message, "username_value": username_value})

@router.post("/register", response_class=HTMLResponse, name="handle_registration_form")
async def handle_registration_form(request: Request, username: str = Form(...), password: str = Form(...), password_confirm: str = Form(...)):
    if password != password_confirm:
        return templates.TemplateResponse("register.html", {"request": request, "title": "Register", "error_message": "Passwords do not match.", "username_value": username})

    api_register_url = str(request.url_for('register_new_user')) # API route name
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(api_register_url, json={"username": username, "password": password})
            response.raise_for_status()
            login_url = request.url_for('serve_login_page') + "?message=Registration successful! Please log in."
            return RedirectResponse(url=login_url, status_code=status.HTTP_302_FOUND)
        except httpx.HTTPStatusError as e:
            error_detail = e.response.json().get("detail", "Registration failed.")
            return templates.TemplateResponse("register.html", {"request": request, "title": "Register", "error_message": error_detail, "username_value": username})
        except httpx.RequestError:
            return templates.TemplateResponse("register.html", {"request": request, "title": "Register", "error_message": "Registration service unavailable.", "username_value": username})

# --- Logout Route ---
@router.get("/logout", name="handle_logout")
async def handle_logout(request: Request):
    response = RedirectResponse(url=request.url_for('serve_home_page'), status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response

# --- M365 OAuth Frontend Routes ---
@router.get("/auth/m365/initiate", name="initiate_m365_auth_frontend") # Changed name slightly for clarity
async def initiate_m365_auth_frontend(request: Request):
    if not request.state.user_authenticated:
        return RedirectResponse(url=request.url_for('serve_login_page') + "?error_message=Please log in to connect M365.", status_code=status.HTTP_302_FOUND)
    backend_api_authorize_url = str(request.url_for('m365_authorize_redirect')) # API route name
    return RedirectResponse(url=backend_api_authorize_url, status_code=status.HTTP_302_FOUND)

@router.post("/auth/m365/disconnect", name="handle_m365_disconnect")
async def handle_m365_disconnect(request: Request):
    if not request.state.user_authenticated:
        return RedirectResponse(url=request.url_for('serve_login_page') + "?error_message=Please log in.", status_code=status.HTTP_302_FOUND)

    token = get_auth_token_from_cookie(request)
    if not token:
        return RedirectResponse(url=request.url_for('serve_login_page') + "?error_message=Authentication token missing.", status_code=status.HTTP_302_FOUND)

    api_disconnect_url = str(request.url_for('m365_disconnect')) # Name of the new API POST endpoint
    headers = {"Authorization": f"Bearer {token}"}
    message, error = None, None

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(api_disconnect_url, headers=headers)
            response.raise_for_status()
            message = response.json().get("message", "Microsoft 365 account disconnected successfully.")
        except httpx.HTTPStatusError as e:
            error = e.response.json().get("detail", "Failed to disconnect M365 account.")
        except httpx.RequestError:
            error = "M365 disconnect service unavailable."

    redirect_url_params = f"?message={message}" if message else f"?error={error}"
    return RedirectResponse(url=request.url_for('serve_dashboard_page') + redirect_url_params, status_code=status.HTTP_302_FOUND)


# --- Dashboard Page ---
@router.get("/dashboard", response_class=HTMLResponse, name="serve_dashboard_page")
async def serve_dashboard_page(request: Request, page: int = Query(1, ge=1), message: Optional[str] = None, error: Optional[str] = None):
    if not request.state.user_authenticated:
        return RedirectResponse(url=request.url_for('serve_login_page') + "?error_message=Please log in to view dashboard.", status_code=status.HTTP_302_FOUND)

    token = get_auth_token_from_cookie(request)
    if not token: # Should be caught by middleware, but defensive check
        return RedirectResponse(url=request.url_for('serve_login_page') + "?error_message=Authentication token missing.", status_code=status.HTTP_302_FOUND)

    logs_data, api_error_logs = None, error # Preserve error from query param if any for logs
    m365_status_data: Dict[str, Any] = {"is_connected": False, "account_email": None, "error": None}

    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Fetch M365 connection status
        api_m365_status_url = str(request.url_for('get_m365_connection_status')) # API route name
        try:
            status_response = await client.get(api_m365_status_url, headers=headers)
            status_response.raise_for_status()
            m365_status_data = status_response.json() # Directly use the JSON response
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401: # Token issue
                return RedirectResponse(url=request.url_for('serve_login_page') + "?error_message=Session expired. Please log in.", status_code=status.HTTP_302_FOUND)
            m365_status_data["error"] = f"Could not fetch M365 status: {e.response.json().get('detail', e.response.status_code)}"
        except httpx.RequestError:
            m365_status_data["error"] = "M365 status service unavailable."

        # 2. Fetch Activity Logs
        api_logs_url = str(request.url_for('get_activity_logs')) # API route name
        try:
            params = {"page": page, "page_size": 5}
            logs_api_response = await client.get(api_logs_url, headers=headers, params=params)
            logs_api_response.raise_for_status()
            logs_data = logs_api_response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401: # Should have been caught by M365 status check, but good to have
                 return RedirectResponse(url=request.url_for('serve_login_page') + "?error_message=Session expired. Please log in.", status_code=status.HTTP_302_FOUND)
            api_error_logs = f"Failed to load logs: {e.response.json().get('detail', e.response.status_code)}"
        except httpx.RequestError:
            api_error_logs = "Activity logs service unavailable."

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request, "title": "Dashboard",
            "logs_data": logs_data,
            "error_message": api_error_logs or m365_status_data.get("error"), # Show first error
            "success_message": message, # From query param
            "m365_connection_status": m365_status_data
        }
    )

# --- EML Upload Form Handler & Cloud Sync Trigger (Implementations as before) ---
@router.post("/dashboard/upload-eml", name="handle_eml_upload_form")
async def handle_eml_upload_form(request: Request, eml_file: Annotated[UploadFile, File(...)]):
    if not request.state.user_authenticated:
        return RedirectResponse(url=request.url_for('serve_login_page') + "?error_message=Please log in to upload files.", status_code=status.HTTP_302_FOUND)
    token = get_auth_token_from_cookie(request)
    if not token:
         return RedirectResponse(url=request.url_for('serve_login_page') + "?error_message=Authentication token missing.", status_code=status.HTTP_302_FOUND)
    api_upload_url = str(request.url_for('process_eml_upload')) # API route name
    files = {'file': (eml_file.filename, await eml_file.read(), eml_file.content_type)}
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(api_upload_url, files=files, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            success_msg = response_data.get("message", "EML processed.") + f" (Task ID: {response_data.get('task_id', 'N/A')})"
            redirect_url = request.url_for('serve_dashboard_page') + f"?message={success_msg}"
        except httpx.HTTPStatusError as e:
            error_detail = e.response.json().get("detail", "EML processing failed.")
            redirect_url = request.url_for('serve_dashboard_page') + f"?error={error_detail}"
        except httpx.RequestError:
            redirect_url = request.url_for('serve_dashboard_page') + "?error=EML upload service unavailable."
        finally:
            await eml_file.close()
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

@router.post("/dashboard/trigger-cloud-sync", name="handle_cloud_sync_trigger")
async def handle_cloud_sync_trigger(request: Request, max_emails: int = Form(10), mark_as_read: bool = Form(True)):
    if not request.state.user_authenticated:
        return RedirectResponse(url=request.url_for('serve_login_page') + "?error_message=Please log in to trigger cloud sync.", status_code=status.HTTP_302_FOUND)
    token = get_auth_token_from_cookie(request)
    if not token:
        return RedirectResponse(url=request.url_for('serve_login_page') + "?error_message=Authentication token missing.", status_code=status.HTTP_302_FOUND)
    # API route name for triggering cloud sync (task queueing)
    api_sync_url = str(request.url_for('trigger_cloud_mailbox_sync')) + f"?max_emails={max_emails}&mark_as_read={mark_as_read}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(api_sync_url, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            success_msg = response_data.get("message", "Cloud sync initiated.") + f" (Task ID: {response_data.get('task_id', 'N/A')})"
            redirect_url = request.url_for('serve_dashboard_page') + f"?message={success_msg}"
        except httpx.HTTPStatusError as e:
            error_detail = e.response.json().get("detail", "Cloud sync failed.")
            redirect_url = request.url_for('serve_dashboard_page') + f"?error={error_detail}"
        except httpx.RequestError:
            redirect_url = request.url_for('serve_dashboard_page') + "?error=Cloud sync service unavailable or timed out."
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
