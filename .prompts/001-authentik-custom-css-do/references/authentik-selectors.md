# Authentik HTML Structure Reference

Source: Single-file export of the authentik login page (avatar-authentication-flow, dark theme).

## Key Elements (from page DOM)

### Top-level web component
```html
<ak-flow-executor slug=avatar-authentication-flow class="pf-c-login"
  data-layout=stacked data-test-id=interface-root theme=dark>
```
- This is the root element for ALL flows (login, recovery, enrollment, etc.)
- Custom CSS in `branding_custom_css` applies to the page's global stylesheet,
  so `ak-flow-executor { }` is the correct scope selector for flows.
- Does NOT affect admin interface.

### Locale selector (shadow DOM)
```html
<ak-locale-select part=locale-select
  exportparts="label:locale-select-label,select:locale-select-select"
  class="style-scope ak-flow-executor" theme=dark>
  <label part=label for=locale-selector aria-label="Select language">...</label>
  <select part=select id=locale-selector class="pf-c-form-control ak-m-capitalize">...</select>
```
- In shadow DOM — CANNOT be styled with regular CSS selectors
- Use `ak-flow-executor::part(locale-select)` to style host element
- Use `ak-flow-executor::part(locale-select-label)` for the globe icon label
- Use `ak-flow-executor::part(locale-select-select)` for the dropdown

### Login card
```html
<main class="pf-c-login__main style-scope ak-flow-executor">
  <div class="pf-c-login__main-header pf-c-brand style-scope ak-flow-executor">
  <div class="pf-c-login__main-header style-scope ak-flow-card">
  <div class="pf-c-login__main-body style-scope ak-flow-card">
  <div class="pf-c-login__main-footer style-scope ak-flow-card">
```

### Login/submit button
```html
<button class="pf-c-button pf-m-primary pf-m-block style-scope ak-stage-identification">
```
- PatternFly v5 (2025.12+) uses `pf-v5-c-button` class prefix
- Pre-2025.12 uses `pf-c-button` prefix
- Include both variants in CSS

### "Powered by authentik" footer
```html
<ak class="pf-c-login__footer pf-m-dark">
  <ak-brand-links>
    <ul class="pf-c-list pf-m-inline style-scope ak-brand-links" part=list>
      <li part=list-item><span>Powered by authentik</span></li>
    </ul>
  </ak-brand-links>
</ak>
```
- The footer is a custom element `<ak>` with class `pf-c-login__footer`
- `ak-brand-links` contains the "Powered by authentik" text
- Setting `color: transparent` on `.pf-c-login__footer` or `visibility: hidden` on `ak-brand-links`

## PatternFly Version Notes

| Authentik version | PF version | Class prefix |
|---|---|---|
| ≤ 2025.10 | PF v4 | `pf-c-*` |
| ≥ 2025.12 | PF v5 | `pf-v5-c-*` |

Always include BOTH `pf-c-*` and `pf-v5-c-*` variants in CSS to be safe across upgrades.

## CSS Variables (from page source)

| CSS variable | Controls |
|---|---|
| `--pf-global--primary-color--300` | Primary button hover background |
| `--pf-global--primary-color--100` | Primary button background |
| `--pf-global--BackgroundColor--100` | Card/form background |
| `--pf-global--Color--100` | Default text / locale picker color |
| `--pf-global--link--Color` | Link color |
| `--pf-global--link--Color--hover` | Link hover color |

## Known Issues

### Issue #19556 — Custom CSS stopped working in 2025.12
- Direct class selectors often fail; use CSS custom properties + `!important`
- Include both `pf-c-*` and `pf-v5-c-*` variants

### Issue #19506 — Locale selector not styleable via regular CSS
- Fixed by using `ak-flow-executor::part(locale-select)` (::part pseudo-element)
- `exportparts` attribute re-exports inner parts for external styling

### Issue #14958 — Font families with quoted strings don't work in inline blueprint YAML
- Workaround: use file mount + `@import url()` in blueprint (no YAML quoting issue)

### Issue #15149 — No file-path support for branding_custom_css in blueprints
- Authentik maintainer won't add native file support
- Workaround: mount CSS file to `/web/dist/custom.css` → served at `/static/dist/custom.css`
- Blueprint sets: `branding_custom_css: "@import url('/static/dist/custom.css');"`

### Issue #20275 — Admin dashboard buttons not styleable from branding CSS
- Admin wizard uses deeply nested shadow DOM
- Scoping custom CSS to `ak-flow-executor { }` naturally avoids this issue
