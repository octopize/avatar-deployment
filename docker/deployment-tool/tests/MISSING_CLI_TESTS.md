# Missing CLI Integration Test Coverage

> **QA Test Engineer Analysis** - Comprehensive list of missing integration tests for the Avatar Deployment Tool CLI

## CLI Arguments Reference

```
--output-dir <path>          Output directory for generated files (default: current directory)
--template-from <source>     Template source: 'github' or path to local templates (default: github)
--config <file>              YAML configuration file to load
--non-interactive            Run in non-interactive mode (use defaults or config file)
--save-config                Save configuration to deployment-config.yaml
--verbose                    Verbose output
```

**Note**: Templates are always stored at `output-dir/.avatar-templates` regardless of source.

---

## 1. Argument Combination Tests

### Valid Combinations (Should Succeed)

- `--save-config --non-interactive --config <file>`
  - Load config from file, run non-interactively, then save final config

- `--verbose --save-config`
  - Run with verbose output and save configuration

- `--template-from github --verbose`
  - Download from GitHub with verbose output showing download progress

- `--template-from <local-path> --verbose`
  - Copy from local templates directory with verbose output

- `--config <file> --save-config`
  - Load existing config, potentially modify interactively, then save (round-trip test)

### Invalid/Error Combinations (Should Fail with Helpful Messages)

- `--config <non-existent-file>`
  - **Expected**: Clear error "Config file not found: <path>"

- `--config <malformed-yaml>`
  - **Expected**: YAML parse error with line number and helpful message

- `--non-interactive` (without `--config`)
  - **Expected**: Should either succeed with all defaults OR fail with message "Non-interactive mode requires --config"

- `--output-dir /read-only-path`
  - **Expected**: Permission denied error with clear message

- `--template-from /non-existent`
  - **Expected**: "Template source directory not found: /non-existent"

- `--template-from <empty-directory>`
  - **Expected**: "No template files found in <directory>"

- `--config <file>` with missing required fields
  - **Expected**: Clear error listing missing required fields. Make sure it compares versions.

- `--output-dir ""`
  - **Expected**: Invalid path error

- `--template-from ""`
  - **Expected**: Invalid template source error

---

## 2. Save Config Feature Tests

**Currently Missing:**

- `--save-config` in interactive mode
  - Verify config saved correctly after all interactive responses
  - Verify saved file has correct YAML structure

- `--save-config --config <existing>`
  - Load existing config, modify interactively, save to deployment-config.yaml

- Config round-trip validation
  - Save config, then reload it with `--config deployment-config.yaml --non-interactive`
  - Verify identical output

---

## 3. Template Source Tests

**Currently Missing:**

- `--template-from github` (explicit, this is the default)
  - Verify download from GitHub main branch
  - Uses cached version if available

- `--template-from /local/path`
  - Copy templates from local directory to `output-dir/.avatar-templates`
  - Verify all template files copied correctly

- `--template-from <path>` with partial templates
  - Directory missing some required template files
  - **Expected**: Error listing missing templates

- `--template-from <path>` with corrupt templates
  - Templates with invalid syntax or encoding
  - **Expected**: Template rendering error with helpful message

- `--template-from <non-existent-path>`
  - **Expected**: "Template source directory not found: <path>"

- Template source with wrong permissions
  - Read-only templates directory
  - **Expected**: Should succeed (only reading from source)

- GitHub download failure scenarios
  - Network error simulation
  - **Expected**: Clear error message about download failure

---

## 4. Verbose Mode Tests

**Currently Missing:**

- `--verbose` with successful deployment
  - Verify enhanced output shows:
    - Step-by-step progress
    - File generation details
    - Secret generation count

- `--verbose` with error scenarios
  - Verify error details and stack traces shown

---

## 5. Config File Tests

### Valid Config Files

- **Complete config** - All fields populated
- **Minimal config** - Only required fields
- **SeaweedFS config** - Complete SeaweedFS storage setup
- **S3 config** - AWS S3 storage configuration
- **GCS config** - Google Cloud Storage configuration
- **Azure config** - Azure Blob Storage configuration
- **No telemetry config** - Telemetry disabled
- **With telemetry config** - Telemetry fully configured
- **Email with auth config** - SMTP with username/password
- **Email no auth config** - SMTP without authentication

### Invalid Config Files (Should Fail)

- **Malformed YAML** - Syntax errors, tabs instead of spaces
  - **Expected**: YAML parse error with line number

- **Invalid URL format** - `base_url: "not-a-url"`
  - **Expected**: URL validation error

- **Invalid port** - `smtp_port: "not-a-number"` or negative port
  - **Expected**: Port validation error with acceptable range

- **Type mismatches** - String where int expected, etc.
  - **Expected**: Type error with expected vs actual type

- **Extra unknown fields** - Fields not in schema
  - **Expected**: Should ignore gracefully (or warn if strict mode)

- **Partial config with missing required fields**
  - **Expected**: List missing required fields clearly

- **Conflicting config** - e.g., `use_email_auth: false` but email credentials provided
  - **Expected**: Should use config as-is or warn about unused fields

---

## 6. Non-Interactive Mode Edge Cases

**Currently Missing:**

- `--non-interactive --config <complete-config>`
  - Should succeed fully without any prompts
  - Verify all files generated correctly

- `--non-interactive --config <partial-config>`
  - Test behavior: use defaults for missing values OR fail
  - Document which approach is expected

- `--non-interactive` (no config file)
  - Should use all defaults
  - Verify succeeds or fails with clear message

- `--non-interactive --config <invalid-config>`
  - Should fail immediately with validation errors
  - No partial configuration allowed

---

## 7. Output Directory Tests

**Currently Missing:**

- `--output-dir <existing-dir-with-files>`
  - Directory already contains .env, docker-compose.yml, etc.
  - **Behavior**: Overwrite? Fail? Merge? Document expected behavior

- `--output-dir .`
  - Current directory - common use case

- `--output-dir /tmp/deeply/nested/path/that/doesnt/exist`
  - Should create all parent directories (mkdir -p behavior)

- `--output-dir ~/avatar-deploy`
  - Home directory expansion test

- `--output-dir "path with spaces"`
  - Paths with special characters

- `--output-dir ../relative/path`
  - Relative paths should work

- Output directory creation failure
  - No write permissions in parent directory
  - **Expected**: Clear permission error

---

## 12. State Management/Resumption

**If state management is implemented:**

- **Resume interrupted configuration**
  - Start configuration, interrupt, restart
  - Should prompt to resume or restart

- **Partial state corruption**
  - Manually corrupt state file
  - **Expected**: Detect corruption, prompt to restart

- **State file version mismatches**
  - Old state file format from previous version
  - **Expected**: Migration or restart prompt

- **State with `--non-interactive`**
  - Behavior when state exists but running non-interactively
  - It should use state.

## 14. Edge Cases & Special Scenarios

- **Running twice in same directory**
  - First run completes, run again
  - **Behavior**: It should prompt!

---

## Priority Recommendations

### 🔴 High Priority (Core Functionality)

1. **Config file error handling** - Malformed, missing, invalid values
2. **Non-interactive mode completeness** - With/without config, validation
3. **Save config round-trip** - Save and reload verification
4. **Output directory edge cases** - Permissions, existing files
5. **Template source validation** - Missing, corrupt, or invalid templates

### 🟡 Medium Priority (Common Use Cases)

1. **Verbose mode verification** - Output completeness
2. **Email configuration variants** - Different SMTP setups
3. **Signal handling** - Clean interruption handling
4. **Telemetry variations** - Enabled/disabled scenarios
5. **Path handling** - Special characters, relative paths, home expansion

### 🟢 Low Priority (Advanced/Rare)

1. **State management** - If implemented
2. **Complex multi-flag combinations** - Edge case scenarios
3. **Unicode/encoding** - Non-ASCII paths and values
4. **Concurrent execution** - Multiple processes

---

## Test Implementation Suggestions

### Fixture Organization

```
tests/fixtures/
├── config_files/
│   ├── complete.yaml
│   ├── minimal.yaml
│   ├── malformed.yaml
│   ├── invalid_url.yaml
│   ├── s3_storage.yaml
│   ├── gcs_storage.yaml
│   └── azure_storage.yaml
├── scenarios/
│   ├── basic_deployment/
│   ├── cloud_storage/
│   ├── no_telemetry/
│   └── production_full/
└── templates/
    └── mock-templates/  # For --template-from tests
```

### Error Message Validation

For each error case, verify:

- ✅ Non-zero exit code
- ✅ Clear error message (not just stack trace)
- ✅ Actionable suggestion for user
- ✅ No partial files created (or clean state)

---

## Coverage Metrics Goal

- **Argument combinations**: 30+ test cases
- **Config file scenarios**: 15+ test cases  
- **Storage backends**: 4+ backend types × 2-3 auth methods each
- **Error cases**: 20+ error scenarios with message validation
- **Edge cases**: 10+ special scenarios

**Total estimated**: 100+ new integration test cases for comprehensive CLI coverage
