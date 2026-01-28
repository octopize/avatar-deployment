# Modular Step System Architecture

## Overview

The deployment tool now uses a **component-based step system** where each deployment component (email, database, telemetry, etc.) handles **both its configuration AND secrets** in a single cohesive step.

## Key Improvements

### 1. **Versioned Templates & Compatibility**

**Problem**: Old scripts could break new templates or vice versa.

**Solution**: Version checking prevents incompatibilities:
- Script v0.1.0 can modify templates v0.1.x (same minor)
- Script v0.1.0 **cannot** modify templates v0.2.0 (newer minor)
- Script v0.2.0 **can** modify templates v0.1.0 (backward compatible)

**Files**:
- `version_compat.py` - Compatibility checker
- `defaults.yaml` - Contains version: "0.1.0"
- `docker/.template-version` - Template version file

### 2. **Modular Component Steps**

**Problem**: Config and secrets were split across different steps, making it hard to add new components (e.g., authentik).

**Solution**: Each component is a self-contained step:

```python
class EmailStep(DeploymentStep):
    """Handles ALL email-related config and secrets"""
    
    def collect_config(self):
        # Returns: MAIL_PROVIDER, SMTP_HOST, etc.
    
    def generate_secrets(self):
        # Returns: smtp_password, aws_access_key_id, etc.
```

**Benefits**:
- ✅ Add new components easily (e.g., `AuthentikStep`)
- ✅ Each component owns its config + secrets
- ✅ Steps are independent and testable
- ✅ Clear separation of concerns

### 3. **Dynamic Step Registration**

**Problem**: Steps were hardcoded in `state_manager.py`.

**Solution**: Steps are registered dynamically:

```python
step_classes = [
    RequiredConfigStep,
    EmailStep,
    DatabaseStep,
    TelemetryStep,
    StorageStep,
]

# State manager uses dynamic step names
step_names = [cls.name for cls in step_classes]
state = DeploymentState(state_file, steps=step_names)
```

**Benefits**:
- ✅ Easy to add/remove/reorder steps
- ✅ Steps defined in separate files
- ✅ State manager is generic

## File Structure

```
deployment-tool/
├── configure.py              # Main orchestrator
├── state_manager.py          # Generic state management (dynamic steps)
├── download_templates.py     # Template downloader
├── version_compat.py         # Version compatibility checker
├── defaults.yaml             # Defaults + version
├── steps/
│   ├── __init__.py          # Exports all steps
│   ├── base.py              # DeploymentStep base class
│   ├── required.py          # RequiredConfigStep
│   ├── email.py             # EmailStep (config + secrets)
│   ├── database.py          # DatabaseStep (config + passwords)
│   ├── telemetry.py         # TelemetryStep (sentry, logs)
│   └── storage.py           # StorageStep (S3, app secrets)
└── EXAMPLE_NEW_STEPS.py     # Example of using new system
```

## Current Steps

### 1. RequiredConfigStep
- **Config**: PUBLIC_URL, ENV_NAME, AVATAR_HOME, service versions
- **Secrets**: None
- **Required**: Yes

### 2. EmailStep
- **Config**: MAIL_PROVIDER, SMTP_HOST, SMTP_PORT, etc.
- **Secrets**: smtp_password, aws_access_key_id, aws_secret_access_key
- **Required**: Yes

### 3. DatabaseStep
- **Config**: Database names (authentik, avatar, postgres)
- **Secrets**: db_password, authentik_db_password
- **Required**: Yes

### 4. TelemetryStep
- **Config**: IS_SENTRY_ENABLED, TELEMETRY_S3_ENDPOINT_URL, LOG_LEVEL, USE_CONSOLE_LOGGING
- **Secrets**: sentry_dsn (optional)
- **Required**: No (can be skipped)

### 5. StorageStep
- **Config**: DATASET_EXPIRATION_DAYS, USE_EMAIL_AUTHENTICATION
- **Secrets**: avatar_api_encryption_key, authentik_secret_key, seaweedfs credentials
- **Required**: Yes

## Adding a New Component (e.g., Authentik)

### Before (Old System):
```python
# Would need to:
1. Add config collection in prompt_for_config()
2. Add secrets in create_secrets()
3. Split logic across multiple places
```

### After (New System):
```python
# steps/authentik.py
class AuthentikStep(DeploymentStep):
    name = "authentik"
    description = "Configure Authentik SSO"
    required = True
    
    def collect_config(self):
        return {
            "AUTHENTIK_URL": f"https://{self.config['PUBLIC_URL']}/sso",
            "AUTHENTIK_BOOTSTRAP_PASSWORD": "admin",  # Will prompt
            # ... other authentik config
        }
    
    def generate_secrets(self):
        return {
            "authentik_secret_key": secrets.token_urlsafe(50),
            "authentik_bootstrap_token": secrets.token_hex(32),
            # ... other authentik secrets
        }

# In configure.py, just add to the list:
step_classes = [
    RequiredConfigStep,
    EmailStep,
    DatabaseStep,
    AuthentikStep,  # <-- Add here
    TelemetryStep,
    StorageStep,
]
```

That's it! The step is now integrated.

## Version Compatibility Example

```python
# Script v0.1.0 trying to use template v0.2.0
from version_compat import check_compatibility

check_compatibility("0.1.0", "0.2.0")
# Raises: VersionError: Script v0.1.0 cannot modify template v0.2.0

# Script v0.2.0 using template v0.1.0
check_compatibility("0.2.0", "0.1.0")
# OK! Newer scripts can use older templates (backward compatible)
```

## State Management with Dynamic Steps

```yaml
# .deployment-state.yaml
version: "1.0"
steps:
  required_config: completed
  email: completed
  database: in-progress
  telemetry: not-started
  storage: not-started
config:
  PUBLIC_URL: avatar.example.com
  ENV_NAME: mycompany-prod
  MAIL_PROVIDER: smtp
step_data:
  required_config:
    config: {...}
    secrets: []
  email:
    config: {...}
    secrets: ["smtp_password"]
```

## Migration Path

### Current Files to Update:
1. ✅ `defaults.yaml` - Add version
2. ✅ `docker/.template-version` - Create version file
3. ⏳ `configure.py` - Refactor to use new steps
4. ✅ `state_manager.py` - Support dynamic steps
5. ✅ `pyproject.toml` - Include steps/ directory

### Testing:
```bash
cd deployment-tool
pytest tests/  # Existing tests
python EXAMPLE_NEW_STEPS.py  # Test new system
```

## Benefits Summary

| Aspect | Old System | New System |
|--------|-----------|------------|
| Adding component | Edit multiple files | Create one step file |
| Config + Secrets | Split across steps | Together in one step |
| Step definition | Hardcoded | Dynamic registration |
| Version safety | None | Automatic checking |
| Testability | Monolithic | Isolated steps |
| File organization | Single configure.py | Separate step files |

## Next Steps

1. Update `configure.py` to use the new step system
2. Test with all presets (default, dev-mode, airgapped)
3. Update tests to cover new step classes
4. Document preset + step interaction
5. Add `AuthentikStep` as example of extensibility
