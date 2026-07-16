# Microsoft Entra Login

This project can use Microsoft Entra ID through the existing OIDC authorization-code-with-PKCE
flow.

## Azure App Registration

1. Create an app registration in Microsoft Entra ID.
2. Add a redirect URI for the web app, for example `http://localhost:3001`.
3. Create a client secret for the API code exchange.
4. Expose an API scope such as `api://<application-client-id>/access_as_user`.
5. Optionally configure group or app-role claims if you want Entra groups to drive application
   roles.

## Local Environment

Set these values in `.env`:

```bash
DEV_AUTH_ENABLED=false
NEXT_PUBLIC_AUTH_MODE=oidc
MICROSOFT_TENANT_ID=<tenant-id>
NEXT_PUBLIC_MICROSOFT_TENANT_ID=<tenant-id>
OIDC_CLIENT_ID=<application-client-id>
NEXT_PUBLIC_OIDC_CLIENT_ID=<application-client-id>
OIDC_CLIENT_SECRET=<client-secret-value>
OIDC_AUDIENCE=api://<application-client-id>
OIDC_AUTO_PROVISION_USERS=true
NEXT_PUBLIC_OIDC_REDIRECT_URI=http://localhost:3001
NEXT_PUBLIC_OIDC_SCOPE="openid profile email offline_access api://<application-client-id>/access_as_user"
```

The Microsoft preset derives these endpoints automatically:

- `https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/authorize`
- `https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token`
- `https://login.microsoftonline.com/<tenant-id>/discovery/v2.0/keys`
- `https://login.microsoftonline.com/<tenant-id>/v2.0`

## Role Mapping

For a personal Azure account demo, `OIDC_AUTO_PROVISION_USERS=true` creates a local user on first
successful Microsoft sign-in with the `employee` role. In stricter environments, leave auto
provisioning disabled and seed approved users explicitly.

To synchronize Entra groups or app roles to local roles, set `OIDC_GROUP_ROLE_MAP_JSON`:

```json
{
  "<platform-admin-group-object-id>": ["platform_admin"],
  "<auditor-group-object-id>": ["security_auditor"]
}
```

With no group mapping configured, users keep the roles seeded in the database.
