# Authentik Email Templates

**Single source of truth** for authentik email templates. Uses Django template syntax.

## Files

- `email_password_reset.html` - Password reset emails (authentik default)
- `email_account_confirmation.html` - Email verification (authentik default)
- `email_account_exists.html` - Notification when account already exists (authentik default)
- `email_account_invitation.html` - Account creation/invitation emails (custom)
- `email_forgotten_password.html` - Password reset request emails (custom)
- `email_password_changed.html` - Password changed confirmation (custom)

## Available Variables

- `{{ url }}` - Action URL
- `{{ user.name }}` - User's display name
- `{{ user.email }}` - User's email
- `{{ expires }}` - Link expiration (hours)

## Workflow

1. **Edit** templates in this directory
2. **Sync** to deployment targets: `./sync-templates.sh`
3. **Test** Docker: `cd docker && docker-compose restart authentik_server authentik_worker`
4. **Deploy** Helm: `cd helm && just package`

⚠️ **Do not edit** `docker/authentik/custom-templates/` or `services-api-helm-chart/templates-files/` - they're auto-synced.

Docs: https://goauthentik.io/docs/flow/stages/email/
