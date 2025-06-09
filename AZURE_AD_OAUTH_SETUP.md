# Azure AD Application Registration for Microsoft 365 OAuth 2.0 (Delegated Permissions)

This document guides you through configuring an Azure Active Directory (Azure AD)
application to allow users to authenticate and authorize this application
to access their Microsoft 365 mailbox data (e.g., read emails) using the
OAuth 2.0 authorization code grant flow with delegated permissions. This is typically
used when the application needs to act on behalf of a signed-in user.

## Prerequisites

*   An Azure account with an active subscription.
*   Permissions to register applications in Azure AD (typically Global Administrator,
    Application Administrator, or Application Developer roles).

## Steps for App Registration or Modification

You might be modifying an existing App Registration (e.g., one previously used for app-only client credentials flow) or creating a new one. For user-delegated permissions, specific configurations for "Redirect URIs" and "API permissions" are crucial.

1.  **Navigate to Azure Active Directory:**
    *   In the Azure portal (`portal.azure.com`), search for and select "Azure Active Directory".

2.  **App Registrations:**
    *   Select "App registrations" from the left navigation pane.
    *   **To create a new app:**
        *   Click "+ New registration".
        *   **Name:** Provide a meaningful name (e.g., "Activity Logger M365 User Auth").
        *   **Supported account types:** Choose the appropriate option. For allowing users from your organization only, select "Accounts in this organizational directory only (Single tenant)". For broader access, consider other options.
        *   **Redirect URI (Platform: Web):** This is critical. You must register the exact URIs where Microsoft will send the authorization code after user consent.
            *   Enter a temporary or primary redirect URI here, e.g., `http://localhost:8000/api/v1/auth/m365/callback` for local development. You can add more later.
        *   Click "Register".
    *   **To modify an existing app:**
        *   Find and select your existing application from the list.

3.  **Authentication Configuration:**
    *   In your app registration, go to the "Authentication" blade.
    *   **Platform configurations:**
        *   If you haven't added a "Web" platform, click "+ Add a platform" and select "Web".
        *   **Redirect URIs:** Add all URIs that your application will use for the OAuth 2.0 callback. These must exactly match the `M365_REDIRECT_URI` your application's backend will use to receive the authorization code.
            *   Example for local development: `http://localhost:8000/api/v1/auth/m365/callback`
            *   Example for a production deployment: `https://your-production-app-domain.com/api/v1/auth/m365/callback`
            *   Example for a staging environment: `https://your-staging-app-domain.com/api/v1/auth/m365/callback`
        *   **Front-channel logout URL:** (Optional for this application's current scope)
        *   **Implicit grant and hybrid flows:** For the Authorization Code Flow, ensure "Access tokens" and "ID tokens" under this section are **unchecked**.
    *   Click "Save" at the top if you made changes.

4.  **API Permissions (Delegated):**
    *   Go to the "API permissions" blade.
    *   Review existing permissions. If you were previously using app-only permissions (Application permissions) for a single mailbox, those are different from user-delegated permissions.
    *   Click "+ Add a permission".
    *   Select "Microsoft Graph".
    *   Select "Delegated permissions" (The application accesses the API as the signed-in user).
    *   Search for and add the following permissions:
        *   `Mail.Read`: Allows the application to read email in the signed-in user's mailbox. (Or `Mail.ReadWrite` if needed, but always request least privilege).
        *   `User.Read`: Allows users to sign-in to the app, and allows the app to read the profile of signed-in users. This is often a default.
        *   `offline_access`: **Essential** for obtaining refresh tokens. Refresh tokens allow your application to obtain new access tokens over longer periods without requiring the user to sign in again every time their access token expires. This is crucial for background sync or maintaining user sessions.
    *   Click "Add permissions" at the bottom.
    *   **Admin Consent:**
        *   Some delegated permissions, even for a single tenant app, might require administrator consent, especially if they grant broad access or if your organization's policies require it.
        *   If you see "Admin consent required" in the status for any permission, an Azure AD administrator may need to grant consent for your organization. If you have admin privileges, you might see a button like "Grant admin consent for [Your Directory Name]". Click this to consent on behalf of all users in your organization (if appropriate). If this button is disabled, you'll need to request an admin to do this.
        *   For multi-tenant apps, admin consent has different implications and might be granted per-tenant by their admins.

5.  **Certificates & Secrets (Client Secret):**
    *   Go to the "Certificates & secrets" blade.
    *   Under the "Client secrets" tab, click "+ New client secret".
    *   Add a description (e.g., "activity_logger_m365_oauth_secret") and choose an expiry period (e.g., 12 months, 24 months).
    *   Click "Add".
    *   **IMPORTANT:** Immediately after creation, copy the **Value** of the client secret and store it securely (e.g., in your password manager or development `.env` file for local testing, and then into Google Secret Manager for cloud deployment). **You will not be able to see this value again after you navigate away from this blade.** This value is your application's `AZURE_CLIENT_SECRET`.

6.  **Overview Blade (Identifiers):**
    *   Navigate to the "Overview" blade of your app registration.
    *   Note down the following values:
        *   **Application (client) ID:** This is your `AZURE_CLIENT_ID`.
        *   **Directory (tenant) ID:** This is your `AZURE_TENANT_ID`.

## Application Environment Variables for M365 OAuth

Your application backend will need the following environment variables configured to use this OAuth 2.0 user-delegated flow:

*   `AZURE_CLIENT_ID`: The Application (client) ID obtained from the Azure portal.
*   `AZURE_CLIENT_SECRET`: The **Value** of the client secret you generated and saved.
*   `AZURE_TENANT_ID`: The Directory (tenant) ID.
*   `M365_AUTHORITY`: (Can be constructed by the application) The authority URL, typically `https://login.microsoftonline.com/{AZURE_TENANT_ID}`. For multi-tenant apps or specific clouds, this might vary (e.g., `https://login.microsoftonline.com/common` or `https://login.microsoftonline.com/organizations`).
*   `M365_REDIRECT_URI`: The **exact** redirect URI that your application backend is configured to handle and that is registered in Azure AD for the specific environment (e.g., `http://localhost:8000/api/v1/auth/m365/callback` for local, `https://yourdomain.com/api/v1/auth/m365/callback` for production).
*   `M365_SCOPES`: A space-separated string of scopes your application requests. These must match the delegated permissions configured in Azure AD.
    *   Example: `"Mail.Read User.Read offline_access"`
*   `M365_TOKEN_ENCRYPTION_KEY`: **A crucial security key for encrypting stored refresh tokens.** This must be a URL-safe base64-encoded 32-byte key. You can generate one using Python:
    ```python
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    print(key) # Use this output for the environment variable
    ```
*   `STATE_SERIALIZER_SECRET_KEY`: A secret key used by `itsdangerous` to sign the OAuth `state` parameter stored in a cookie. This helps prevent CSRF attacks during the OAuth flow. It should be a strong, random string. For simplicity in development, it can be set to the same value as `JWT_SECRET_KEY`, but a unique key is recommended for production.

Ensure these are configured securely in your application's environment (e.g., via `.env` file for local development, and Google Secret Manager for cloud deployments, referenced by your `cloudbuild.yaml` or `service.yaml`).
The `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, and `AZURE_TENANT_ID` are the same credentials that might have been used for the app-only client credentials flow, but the permissions and redirect URI setup are specific to the user-delegated OAuth flow.
```
