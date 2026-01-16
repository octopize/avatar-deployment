---
name: authentik-email-templates
description: Create and edit professional email templates for Authentik SSO authentication flows. Use when working with Authentik email templates (.html files) for authentication events such as password reset, account confirmation, email verification, account exists notifications, invitations, or any other Authentik email communication. This skill provides templates, styling patterns, Django template syntax guidance, and deployment workflows for the avatar-deployment project.
---

# Authentik Email Templates

Create professional, branded email templates for Authentik authentication flows.

## Quick Start

1. **Choose a base template** from `assets/` matching your email type
2. **Customize content** with appropriate text and Django variables (business casual tone, no emojis)
3. **Apply color scheme** from [color-schemes.md](references/color-schemes.md) based on email purpose
4. **Test variables** using [authentik-variables.md](references/authentik-variables.md) 
5. **Save to correct location**: `common/authentik-templates/`

## Template Structure

All Authentik email templates follow this pattern:

```html
{# Django comment describing template purpose #}
<!DOCTYPE html>
<html lang="en">
<head>
    <!-- Meta tags and title -->
    <style>
        /* Inline CSS for email client compatibility */
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <!-- Colored header with title (no emojis) -->
        </div>
        <div class="content">
            <!-- Main email body with {{ user.name }} and {{ url }} -->
        </div>
        <div class="footer">
            <!-- Standard Octopize footer -->
        </div>
    </div>
</body>
</html>
```

## Available Templates

Use these as starting points:

- **base-template.html** - General purpose with button action
- **notification-template.html** - Info-only, no action button

## Tone and Style

- **Tone**: Business casual - professional yet approachable
- **No emojis**: Keep headers clean and text-based
- **Clarity**: Direct, clear language that respects user's time
- **Professionalism**: Maintain Octopize brand standards

## Common Email Types

### Password Reset
- **Header**: "Password Reset"
- **Color**: Darker Teal gradient (Octopize brand)
- **Variables**: `{{ url }}`, `{{ expires }}`, `{{ user.name }}`
- **Include**: Warning box about expiration

### Account Confirmation
- **Header**: "Welcome" or "Confirm Your Account"
- **Color**: Primary Teal gradient (Octopize brand)
- **Variables**: `{{ url }}`, `{{ user.name }}`
- **Include**: Welcoming message

### Account Already Exists
- **Header**: "Account Notification"
- **Color**: Primary Teal gradient
- **Variables**: `{{ user.email }}`
- **Include**: Info box with password reset link

### Invitation
- **Header**: "You're Invited" or "Account Invitation"
- **Color**: Primary Teal gradient
- **Variables**: `{{ url }}`, `{{ expires }}`, `{{ invitation }}`

## Django Template Syntax

Authentik uses Django templates. Key patterns:

```django
{# Comments #}
{{ variable }}
{{ user.name|default:"there" }}

{% if condition %}...{% endif %}
{% for item in list %}...{% endfor %}
```

See [authentik-variables.md](references/authentik-variables.md) for complete reference.

## Styling Guidelines

### Must-Have Elements

1. **Inline CSS** - Email clients don't support external stylesheets
2. **Max width 600px** - Optimal for mobile and desktop
3. **Web-safe fonts** - Segoe UI, Arial, sans-serif fallbacks
4. **Responsive design** - `viewport` meta tag, mobile-friendly buttons

### Color Usage

Match colors to email purpose using Octopize brand palette:
- **Teal (Primary)**: Welcome, confirmation, general communications
- **Darker Teal**: Security, passwords, authentication  
- **Amber**: Warnings, expiration notices
- **Red-Orange**: Critical alerts, account suspension

See [color-schemes.md](references/color-schemes.md) for exact color codes.

### Button Best Practices

```html
<center>
    <a href="{{ url }}" class="button">Action Text</a>
</center>
<p>Or copy and paste this link into your browser:</p>
<p style="word-break: break-all; color: #43e97b; font-size: 14px;">{{ url }}</p>
```

Always provide both button and plain text URL for accessibility.

## Deployment Workflow

After creating/editing templates in `common/authentik-templates/`:

1. **Sync to deployment targets**:
   ```bash
   ./sync-templates.sh
   ```
   This syncs to `docker/authentik/custom-templates/` and `services-api-helm-chart/templates-files/`



⚠️ **Never edit** `docker/authentik/custom-templates/` or `services-api-helm-chart/templates-files/` directly - they are auto-synced.

## File Naming Convention

Templates must match Authentik's expected names:

- `email_password_reset.html`
- `email_account_confirmation.html`
- `email_account_exists.html`
- Custom stages: Match the stage's template name configuration


## Common Variables

Most frequently used:

- `{{ user.name }}` - User's display name
- `{{ user.email }}` - User's email
- `{{ url }}` - Action URL (reset, confirm, etc.)
- `{{ expires }}` - Link expiration in hours

## Testing Checklist

Before deployment:

- [ ] Business casual tone throughout
- [ ] No emojis in headers or content
- [ ] All Django variables render correctly
- [ ] Button link uses `{{ url }}`
- [ ] Fallback text URL included
- [ ] Octopize brand colors applied correctly
- [ ] Footer includes copyright year
- [ ] Template comment at top describes purpose
- [ ] No external CSS or JavaScript
- [ ] Responsive on mobile preview

## Examples from Codebase

Reference existing templates in `common/authentik-templates/`:

- `email_password_reset.html` - Security-focused with warning box
- `email_account_confirmation.html` - Professional welcome message
- `email_account_exists.html` - Informative with helpful guidance

## Additional Resources

- **Variables reference**: [authentik-variables.md](references/authentik-variables.md)
- **Color schemes**: [color-schemes.md](references/color-schemes.md)
- **Authentik docs**: https://goauthentik.io/docs/flow/stages/email/
