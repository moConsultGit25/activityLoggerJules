# Google Cloud Project & Gmail API OAuth 2.0 Setup

This document guides you through setting up a Google Cloud Project and configuring
OAuth 2.0 credentials to allow this application to access users' Gmail data
(e.g., read emails) on their behalf using the Gmail API via the OAuth 2.0
authorization code grant flow.

## Prerequisites

*   A Google account (e.g., a Gmail account or a Google Workspace account).
*   Access to the Google Cloud Console ([console.cloud.google.com](https://console.cloud.google.com/)).

## Steps

### 1. Create or Select a Google Cloud Project

1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  If you have an existing project you wish to use, select it from the project dropdown at the top of the page.
3.  Otherwise, click the project dropdown and then "NEW PROJECT".
    *   Enter a **Project name** (e.g., "Activity Logger Gmail Integration").
    *   Select a **Billing account** if prompted (required for using many GCP services, including some APIs beyond their free tier).
    *   Select an **Organization** and **Location** if applicable.
    *   Click "CREATE".

### 2. Enable the Gmail API

1.  Ensure your desired project is selected in the Google Cloud Console.
2.  In the navigation menu (☰), go to "APIs & Services" > "Library".
3.  In the search bar, type "Gmail API" and select it from the results.
4.  Click the "Enable" button. If it's already enabled, this button might not be present or will show "Manage".

### 3. Configure the OAuth Consent Screen

The OAuth consent screen is what users will see when your application asks them to grant permission to access their Google account data (like Gmail).

1.  In the navigation menu, go to "APIs & Services" > "OAuth consent screen".
2.  **User Type:**
    *   **External:** Choose this if your application will be used by any Google user (e.g., users with `@gmail.com` accounts or users from other Google Workspace organizations).
        *   Note: Apps using sensitive/restricted scopes and marked as "External" will likely need to go through Google's app verification process to be generally available. During development, you can add test users.
    *   **Internal:** Choose this if your application is intended only for users within your own Google Workspace organization. This option might not require app verification.
    *   Click "CREATE".
3.  **App information:**
    *   **App name:** Enter a user-facing name for your application (e.g., "Activity Logger - Gmail Access").
    *   **User support email:** Select or enter an email address where users can contact you for support.
    *   **App logo:** (Optional) Upload a logo for your application.
4.  **App domain (Optional but Recommended):**
    *   **Application home page:** URL of your application's home page.
    *   **Application privacy policy URL:** Link to your app's privacy policy.
    *   **Application terms of service URL:** Link to your app's terms of service.
    *   Fill these if applicable, especially for public-facing or "External" apps.
5.  **Authorized domains:**
    *   Add the domain(s) from which your application will be making OAuth requests. For example, if your app is hosted at `https://myapp.example.com`, add `example.com`. This is important for security. `localhost` is typically allowed for development without explicit listing here if using `http://localhost` redirect URIs.
6.  **Developer contact information:**
    *   Enter one or more email addresses for Google to contact you with updates about your project.
    *   Click "SAVE AND CONTINUE".
7.  **Scopes:**
    *   On the "Scopes" page, click "+ ADD OR REMOVE SCOPES".
    *   You need to add scopes that your application requires for the Gmail API.
    *   Use the filter or browse for "Gmail API".
    *   Select the following essential scopes (or more permissive ones if absolutely necessary, always adhering to the principle of least privilege):
        *   `https.www.googleapis.com/auth/gmail.readonly`: To read emails (recommended for this application's current scope). If you later need to modify emails (e.g., mark as read, move), you might use `https://www.googleapis.com/auth/gmail.modify`.
        *   `openid`: To authenticate the user (standard OpenID Connect scope).
        *   `https://www.googleapis.com/auth/userinfo.email` (or just `email`): To get the user's email address.
        *   `https://www.googleapis.com/auth/userinfo.profile` (or just `profile`): To get basic profile information.
    *   Click "UPDATE" after selecting the scopes.
    *   Review the selected scopes and click "SAVE AND CONTINUE".
8.  **Test users (if User Type is "External" and Publishing status is "Testing"):**
    *   If your app is in the "Testing" publishing status, you must add the Google accounts (email addresses) of users who will be allowed to test the application. Only these users will be able to go through the OAuth flow.
    *   Click "+ ADD USERS" and enter the email addresses.
    *   Click "SAVE AND CONTINUE".
9.  **Summary:**
    *   Review the summary of your OAuth consent screen configuration.
    *   Click "BACK TO DASHBOARD".
    *   If your app is "External" and uses sensitive/restricted scopes, you might see a notice about app verification. For development, you can proceed with test users. For production release to external users, app verification by Google might be required.

### 4. Create OAuth 2.0 Client ID Credentials

This will generate the Client ID and Client Secret that your application backend uses to identify itself to Google's OAuth 2.0 servers.

1.  In the navigation menu, go to "APIs & Services" > "Credentials".
2.  Click "+ CREATE CREDENTIALS" at the top and select "OAuth client ID".
3.  **Application type:** Select "Web application" from the dropdown (since our backend handles the OAuth flow).
4.  **Name:** Give your OAuth client ID a descriptive name (e.g., "Activity Logger Web App Client").
5.  **Authorized JavaScript origins:** (Generally not needed for a server-side web app like ours where the backend handles the OAuth code exchange. This is more for frontend JavaScript apps that might initiate parts of the flow directly).
6.  **Authorized redirect URIs:** This is **critical**. Add the URIs where Google will redirect the user (and send the authorization code) after they have authenticated and granted consent. These URIs must exactly match what your application's backend callback endpoint is configured to use.
    *   Click "+ ADD URI".
    *   **Example for local development:** `http://localhost:8000/api/v1/auth/google/callback`
    *   **Example for production:** `https://your-production-app-domain.com/api/v1/auth/google/callback`
    *   Add one URI per line for each environment (development, staging, production).
7.  Click "CREATE".
8.  A dialog box will appear showing **"Your Client ID"** and **"Your Client Secret"**.
    *   **IMPORTANT:** Copy both of these values immediately and store them securely (e.g., in your password manager, and then into your application's secure configuration system like `.env` for local dev or Secret Manager for cloud).
    *   The **Client ID** will be used as the `GOOGLE_CLIENT_ID` environment variable in your application.
    *   The **Client Secret** will be used as the `GOOGLE_CLIENT_SECRET` environment variable.
9.  You can also download the JSON credentials file from this dialog, which contains these values and other configuration details.

## Application Environment Variables for Google OAuth

Your application backend will require the following environment variables to be configured for the Google OAuth 2.0 flow:

*   `GOOGLE_CLIENT_ID`: The Client ID obtained from the "Credentials" page in the Google Cloud Console for your OAuth 2.0 Client ID.
*   `GOOGLE_CLIENT_SECRET`: The Client Secret corresponding to the Client ID.
*   `GOOGLE_REDIRECT_URI`: The primary redirect URI that your application's backend is configured to handle (e.g., `http://localhost:8000/api/v1/auth/google/callback` for local development). This **must** be one of the URIs registered in the "Authorized redirect URIs" section of your OAuth client ID in the Google Cloud Console.
*   `GOOGLE_SCOPES`: A space-separated string of scopes your application requests. These must match or be a subset of the scopes configured in the OAuth consent screen and be appropriate for the APIs you enabled.
    *   Example: `"https://www.googleapis.com/auth/gmail.readonly openid email profile"`
*   `GOOGLE_TOKEN_ENCRYPTION_KEY`: A URL-safe base64-encoded 32-byte key used for encrypting the Google refresh tokens before storing them in your database. This is for added security of the stored tokens.
    *   Generate using Python:
        ```python
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        print(key) # Use this output for the environment variable
        ```
    *   **Keep this key secret!**

Ensure these environment variables are configured securely in your application's environment (e.g., via an `.env` file for local development, and Google Secret Manager for cloud deployments, referenced by your `cloudbuild.yaml` or `service.yaml`).
```
