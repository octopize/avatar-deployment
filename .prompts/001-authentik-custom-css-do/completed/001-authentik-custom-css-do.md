# Implement Authentik Custom CSS - Octopize Brand

## Original User Request

> I already have custom branding images and logo in the authentik blueprint. I want to add custom CSS
> too. I want it to be a file stored in the repo. I want it shared between both docker and Helm. use
> the same pattern we've used for email templates and background-images/logo. I want you to modify the
> authentik custom CSS to be specific to our Octopize brand. I will give you a tailwindcss file from
> our website so that you see the theme. Here is how you can pass the custom css as a file:
> https://github.com/goauthentik/authentik/issues/15149
>
> Do add the fact that I want you to update the deployment tool too. Run the integration tests, update
> the test fixtures, bump template version.
>
> These are the main things I want to change and the css path to the specific elements. I want it to
> target every flow, not just the authentication/login flow (but I don't want it to affect the admin
> view). I also want you to remove the 'Powered by Authentik' footer.
>
> The CSS scope is `ak-flow-executor { }` to target every flow.
> May need to use the part pseudo-element: https://github.com/goauthentik/authentik/issues/19506
>
> Login button:              `--pf-global--primary-color--300`
> Login card background:     `--pf-global--BackgroundColor--100`
> Parent selector:           `.pf-c-login__main.ak-flow-executor`
> Powered by footer:         `.pf-c-login__footer { color }`
> Language picker color:     `[part="locale-select"]` `--pf-global--Color--100`

---

<objective>
Add custom CSS support for authentik SSO, stored as a file in the repository and shared between
Docker Compose and Helm deployments using the same pattern as email templates and branding assets
(common/ → sync-templates.py → deployment targets).

Apply Octopize brand styling to ALL authentication flows (not the admin interface):
- Teal/turquoise primary colour (hsl(165.3, 65.4%, 53.5%))
- Remove "Powered by authentik" footer
- Style locale selector via ::part() pseudo-element

Output artifacts:
- `common/authentik-css/custom.css` — source of truth
- `scripts/sync-templates.py` — add CSS AssetCategory
- `services-api-helm-chart/templates/authentik-custom-css-configmap.yaml` — new ConfigMap
- `services-api-helm-chart/values.yaml` — add CSS volume+mount (worker + server)
- `common/authentik-blueprint/octopize-avatar-blueprint.yaml` — add branding_custom_css field
- `docker/templates/docker-compose.yml.template` — add CSS volume mount
- `deployment-tool/src/octopize_avatar_deploy/download_templates.py` — add CSS to manifest
- `deployment-tool/src/octopize_avatar_deploy/configure.py` — add CSS copy block
- `docker/templates/.template-version` — bump 0.23.0 → 0.24.0
- 7 test fixture docker-compose.yml files updated
- All tests green: `cd deployment-tool && uv run pytest`
</objective>

<context>
<!-- Research references (read these first) -->
HTML structure + CSS selectors: @.prompts/001-authentik-custom-css-do/references/authentik-selectors.md
Proposed CSS (starting point):  @.prompts/001-authentik-custom-css-do/references/proposed-brand.css

<!-- Existing patterns to follow exactly -->
Sync script:               @scripts/sync-templates.py
Branding ConfigMap:        @services-api-helm-chart/templates/authentik-branding-configmap.yaml
Email ConfigMap:           @services-api-helm-chart/templates/authentik-custom-templates-configmap.yaml
Helm values (~215-285):    @services-api-helm-chart/values.yaml
Blueprint (brand section): @common/authentik-blueprint/octopize-avatar-blueprint.yaml
Download manifest:         @deployment-tool/src/octopize_avatar_deploy/download_templates.py
Configure.py (~250-268):   @deployment-tool/src/octopize_avatar_deploy/configure.py
Docker-compose template:   @docker/templates/docker-compose.yml.template
Template version file:     @docker/templates/.template-version

<!-- Test fixtures (all 7 need docker-compose volume mount added) -->
@deployment-tool/tests/fixtures/basic_deployment/expected/docker-compose.yml
@deployment-tool/tests/fixtures/config_round_trip_first/expected/docker-compose.yml
@deployment-tool/tests/fixtures/config_round_trip_second/expected/docker-compose.yml
@deployment-tool/tests/fixtures/dev_mode_deployment/expected/docker-compose.yml
@deployment-tool/tests/fixtures/non_interactive_complete/expected/docker-compose.yml
@deployment-tool/tests/fixtures/no_telemetry/expected/docker-compose.yml
@deployment-tool/tests/fixtures/cloud_storage/expected/docker-compose.yml
</context>

<requirements>
1. CSS file (common/authentik-css/custom.css):
   - Use proposed-brand.css as the starting point — refine as needed
   - Scope with `ak-flow-executor { }` — targets ALL flows, NOT the admin interface
   - Override primary colour to Octopize teal (hsl(165.3, 65.4%, 53.5%))
   - Do NOT change fonts — keep authentik's default font family
   - Include BOTH `pf-c-*` (PF v4, ≤2025.10) AND `pf-v5-c-*` (PF v5, ≥2025.12) class variants
     (issue #19556: 2025.12 changed the PF version; dual support ensures compatibility)
   - Use CSS custom properties at `ak-flow-executor` scope with `!important`
   - Remove "Powered by authentik": hide `ak-brand-links` or set `.pf-c-login__footer { color: transparent }`
   - Style locale selector via `ak-flow-executor::part(locale-select)` and `::part(locale-select-select)`
     (issue #19506: locale selector is in shadow DOM; regular selectors don't reach it)
   - Do NOT use `@layer` or complex SCSS — plain CSS only, browser-compatible
   - Do NOT add any @import for Google Fonts
   - Do NOT set font-family anywhere in the CSS

2. CSS deployment mechanism:
   - Mount the file to `/web/dist/custom.css` inside the authentik container
   - Authentik serves it at `/static/dist/custom.css` (no native file-path support per issue #15149)
   - Blueprint sets: `branding_custom_css: "@import url('/static/dist/custom.css');"`
   - This is a stable workaround — the CSS file remains in git, blueprint inlines just the @import

3. Sync script (scripts/sync-templates.py):
   - Add new AssetCategory for CSS following the exact same pattern as Branding Assets
   - label: "Custom CSS", emoji: 💅 (or 🎨)
   - source_dir: "common/authentik-css"
   - targets: {"Helm chart": "services-api-helm-chart/static/css", "Docker Compose": "docker/authentik/css"}
   - file_patterns: ["*.css"]
   - Update the final git commit hint comment to include new paths

4. Helm ConfigMap (services-api-helm-chart/templates/authentik-custom-css-configmap.yaml):
   - Follow the same pattern as authentik-custom-templates-configmap.yaml
   - Use (.Files.Glob "static/css/*.css").AsConfig (text, not binaryData — CSS is plain text)
   - Name: authentik-custom-css

5. Helm values.yaml — add to BOTH worker AND server sections (they are mirrors):
   Under volumes:
     - name: custom-css
       configMap:
         name: authentik-custom-css
   Under volumeMounts (after last branding mount):
     - name: custom-css
       mountPath: /web/dist/custom.css
       subPath: custom.css
       readOnly: true

6. Blueprint (common/authentik-blueprint/octopize-avatar-blueprint.yaml):
   - Add to the brand entry's attrs block (alongside existing branding_ fields):
     branding_custom_css: "@import url('/static/dist/custom.css');"
   - Do not change any other fields

7. Docker templates (docker/templates/docker-compose.yml.template):
   - Add CSS volume mount to BOTH authentik_server AND authentik_worker services
   - Add after the last branding mount in each service:
     ```yaml
     # Mount custom CSS for Octopize brand styling
     - ./authentik/css/custom.css:/web/dist/custom.css:ro
     ```

8. Deployment tool — download_templates.py:
   - Add to REQUIRED_FILE_MANIFEST under "docker" → "files":
     "authentik/css/custom.css"

9. Deployment tool — configure.py:
   - Add CSS copy block immediately after the branding copy block (~line 268):
     ```python
     # Copy authentik custom CSS
     css_src = self.templates_dir / "authentik" / "css"
     css_dst = self.output_dir / "authentik" / "css"
     if css_src.exists():
         css_dst.mkdir(parents=True, exist_ok=True)
         for css_file in css_src.glob("*"):
             if css_file.is_file():
                 shutil.copy2(css_file, css_dst / css_file.name)
         self.printer.print_success(f"Copied: custom CSS to {css_dst}")
     ```

10. Template version:
    - Bump docker/templates/.template-version from 0.23.0 to 0.24.0
    - This file is read by the deployment tool's version compatibility check
</requirements>

<implementation>

## Execution order

1. Create `common/authentik-css/custom.css` (use proposed-brand.css as base, refine selectors)
2. Update `scripts/sync-templates.py` (add CSS AssetCategory)
3. Create `services-api-helm-chart/templates/authentik-custom-css-configmap.yaml`
4. Update `services-api-helm-chart/values.yaml` (worker + server sections)
5. Update `common/authentik-blueprint/octopize-avatar-blueprint.yaml` (add branding_custom_css)
6. Update `docker/templates/docker-compose.yml.template` (CSS mounts in both services)
7. Update `deployment-tool/src/octopize_avatar_deploy/download_templates.py`
8. Update `deployment-tool/src/octopize_avatar_deploy/configure.py`
9. Bump `docker/templates/.template-version` to 0.24.0
10. Run `./scripts/sync-templates.py --verbose` (creates static/css/ and docker/authentik/css/)
11. Update all 7 test fixture docker-compose.yml files (add CSS volume mount)
    OR use `AVATAR_DEPLOY_UPDATE_FIXTURES=1 cd deployment-tool && uv run pytest` to regenerate them
12. Run `cd deployment-tool && uv run pytest` — all tests must pass

## CSS writing guidelines

The CSS scope is `ak-flow-executor { }`. All custom CSS rules should live inside this scope
OR target elements that only appear in the flow context (not admin).

The recommended modern approach (per GirlBossRush, authentik contributor, comment on #19556):
  > We'll be recommending CSS custom properties and CSS Parts over styles that directly
  > target internal elements. Direct element styling tends to break when authentik updates.

So prefer:
  1. CSS custom properties on `ak-flow-executor` (e.g. `--pf-global--primary-color--300`)
  2. `::part()` pseudo-element for shadow DOM elements
  3. Direct class selectors with `!important` as fallback for both PF v4 + v5

## Do NOT

- Edit `services-api-helm-chart/static/css/` directly — it's a sync target
- Edit `docker/authentik/css/` directly — it's a sync target
- Add admin-scoped CSS (avoid `.pf-c-nav`, `.pf-c-page`, etc. without ak-flow-executor scope)
- Add any font-family or @import for fonts — fonts are intentionally left as-is
</implementation>

<verification>
1. `./scripts/sync-templates.py --dry-run --verbose` — lists CSS as a new category
2. `./scripts/sync-templates.py --verbose` — creates the target files
3. `ls services-api-helm-chart/static/css/custom.css docker/authentik/css/custom.css` — both exist
4. `grep "branding_custom_css" common/authentik-blueprint/octopize-avatar-blueprint.yaml` — present
5. `grep "custom-css\|custom.css" services-api-helm-chart/values.yaml | wc -l` — should be ≥ 4 entries
6. `cd deployment-tool && uv run pytest` — ALL tests pass (run integration tests, update fixtures if needed)
7. `grep -l "custom.css" deployment-tool/tests/fixtures/*/expected/docker-compose.yml | wc -l` — equals 7
8. `cat docker/templates/.template-version` — outputs 0.24.0
</verification>

<output>
Create:
- `common/authentik-css/custom.css`
- `services-api-helm-chart/templates/authentik-custom-css-configmap.yaml`
- `services-api-helm-chart/static/css/custom.css` (generated by sync-templates.py)
- `docker/authentik/css/custom.css` (generated by sync-templates.py)

Modify:
- `scripts/sync-templates.py`
- `services-api-helm-chart/values.yaml`
- `common/authentik-blueprint/octopize-avatar-blueprint.yaml`
- `docker/templates/docker-compose.yml.template`
- `docker/templates/.template-version` (0.23.0 → 0.24.0)
- `deployment-tool/src/octopize_avatar_deploy/download_templates.py`
- `deployment-tool/src/octopize_avatar_deploy/configure.py`
- All 7 fixture docker-compose.yml files

Save summary to: `.prompts/001-authentik-custom-css-do/SUMMARY.md`
</output>

<success_criteria>
- `common/authentik-css/custom.css` exists with Octopize teal CSS (teal buttons/links, no footer, no font changes)
- sync-templates.py syncs CSS to both `services-api-helm-chart/static/css/` and `docker/authentik/css/`
- Helm ConfigMap and values.yaml have CSS volume mounts in both worker and server
- Blueprint has `branding_custom_css: "@import url('/static/dist/custom.css');"`
- docker-compose.yml.template has CSS mount in authentik_server and authentik_worker
- Template version is 0.24.0
- Deployment tool includes CSS in manifest and copy logic
- All 7 fixture docker-compose files include CSS volume mount
- `cd deployment-tool && uv run pytest` passes (ALL tests green)
- SUMMARY.md created with files list and next step
</success_criteria>

<summary_requirements>
Create `.prompts/001-authentik-custom-css-do/SUMMARY.md`

One-liner: Octopize brand CSS added to authentik — teal primary colour, no footer, synced via
common/ pattern to both Helm and Docker Compose.

Include sections:
- Files Created
- Files Modified
- Test Status (all tests passing)
- Next Step: Deploy to staging and visually verify all flows (login, recovery, enrollment, password change)
</summary_requirements>
