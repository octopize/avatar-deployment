# Authentik Email Templates Directory

This directory contains HTML email templates that will be automatically packaged into a ConfigMap for authentik.

## How It Works

1. **Automatic Discovery**: The Helm chart automatically discovers all `.html` files in this directory using `.Files.Glob`
2. **Native Packaging**: Files are packaged during `helm package` without requiring external scripts
3. **Django Template Syntax**: Templates can use Django/authentik syntax (e.g., `{{ url }}`, `{{ user.name }}`) without Helm evaluating them
4. **Direct Mounting**: Each file is mounted individually to `/templates/email/` in authentik pods using `subPath`

## File Naming Convention

authentik expects specific filenames for email templates:

- `email_password_reset.html` - Password reset emails
- `email_account_confirmation.html` - Account verification emails  
- `email_event_notification.html` - Event notification emails
- `email_setup.html` - Initial account setup emails
- `email_test.html` - Test email template

## Adding New Templates

1. Create a new `.html` file in this directory
2. Use Django template syntax for dynamic content:
   ```html
   <a href="{{ url }}">Click here</a>
   <p>Hello {{ user.name }}!</p>
   ```
3. The file will be automatically included in the next `helm package` or `helm install`

## Template Variables Available

Common authentik template variables:

- `{{ url }}` - Action URL (confirmation, password reset, etc.)
- `{{ user.name }}` - User's display name
- `{{ user.email }}` - User's email address
- `{{ expires }}` - Link expiration time (if applicable)
- `{{ event.message }}` - Event message (for notifications)

## Testing

To verify templates are packaged correctly:

```bash
# Package the chart
helm package services-api-helm-chart/

# Extract and inspect
tar -xzf avatar-*.tgz
cat avatar/templates/authentik-custom-templates-configmap.yaml
```

## Notes

- Files must have `.html` extension to be included
- Files are read as raw content - Helm will NOT process `{{ }}` syntax inside them
- Maximum file size should be reasonable for ConfigMap limits (< 1MB per file recommended)
- Templates use UTF-8 encoding
