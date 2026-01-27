# Authentik Email Templates & Branding

**Single source of truth** for authentik email templates and branding assets.

## Email Templates

Uses Django template syntax.

### Files

- `email_password_reset.html` - Password reset emails (authentik default)
- `email_account_confirmation.html` - Email verification (authentik default)
- `email_account_exists.html` - Notification when account already exists (authentik default)
- `email_account_invitation.html` - Account creation/invitation emails (custom)
- `email_forgotten_password.html` - Password reset request emails (custom)
- `email_password_changed.html` - Password changed confirmation (custom)

### Available Variables

- `{{ url }}` - Action URL
- `{{ user.name }}` - User's display name
- `{{ user.email }}` - User's email
- `{{ expires }}` - Link expiration (hours)

## Branding Assets

Source: `../authentik-branding/`

- `favicon.ico` - Browser tab icon
- `logo.png` - Authentik login page logo
- `background.png` - Login page background

## Workflow

1. **Edit** templates or branding in `common/authentik-templates/` or `common/authentik-branding/`
2. **Sync** to deployment targets: `./sync-templates.py`
3. **Test** Docker: `cd docker && docker-compose restart authentik_server authentik_worker`
4. **Deploy** Helm: `cd services-api-helm-chart && just package`

⚠️ **Do not edit** synced directories - they're auto-synced:
- `docker/authentik/custom-templates/`
- `services-api-helm-chart/templates-files/`
- `services-api-helm-chart/branding/`

Docs: https://goauthentik.io/docs/flow/stages/email/
