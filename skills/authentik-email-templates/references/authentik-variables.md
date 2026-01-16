# Authentik Template Variables

Authentik uses Django template syntax for email templates.

## Common Variables

### User Object
- `{{ user.name }}` - User's display name
- `{{ user.email }}` - User's email address
- `{{ user.username }}` - User's username
- `{{ user.uid }}` - User's unique identifier

### Action Variables
- `{{ url }}` - Action URL (password reset, email confirmation, etc.)
- `{{ expires }}` - Link expiration time in hours
- `{{ token }}` - Security token (when applicable)

### Context-Specific Variables

Different email stages provide different context variables:

- **Email Stage**: `{{ url }}`, `{{ expires }}`
- **Invitation Stage**: `{{ url }}`, `{{ expires }}`, `{{ invitation }}` 
- **Enrollment/Recovery**: `{{ url }}`, `{{ expires }}`

## Django Template Syntax

### Comments
```django
{# This is a comment #}
```

### Variables
```django
{{ variable_name }}
```

### Filters
```django
{{ user.name|title }}
{{ expires|default:"24" }}
```

### Conditionals
```django
{% if user.name %}
    Hello {{ user.name }}
{% else %}
    Hello there
{% endif %}
```

### Loops
```django
{% for item in items %}
    {{ item }}
{% endfor %}
```

## Best Practices

1. Always provide fallback values for optional variables
2. Use Django template comments for documentation
3. Test with different user data scenarios
4. Escape user-provided content when necessary

## References

- Authentik Email Stage Docs: https://goauthentik.io/docs/flow/stages/email/
- Django Template Language: https://docs.djangoproject.com/en/stable/ref/templates/language/
