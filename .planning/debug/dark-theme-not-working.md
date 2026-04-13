---
status: resolved
trigger: "Dark theme not working in Electron + Vue + Tailwind app"
created: 2026-04-13T00:00:00Z
updated: 2026-04-13T00:00:00Z
---

## Current Focus

hypothesis: Root cause found and fix applied
test: Updated App.vue background-color from #e8eaf0 to dark gradient
expecting: Dark navy background (#121B26 -> #0F1720) will now display
next_action: Verification by user

## Symptoms

expected: Dark navy background (#121B26 -> #0F1720), glass surfaces with backdrop-blur, off-white text
actual: App showing light neomorphic styling (#e8eaf0 background)
reproduction: Run Electron app after dark theme migration commit (f7802b0)
started: After dark theme migration was committed

## Root Cause

**File:** `electron/src/renderer/App.vue`

**Problem:** The `App.vue` component has a plain CSS `<style>` block defining `.app-shell` with `background-color: #e8eaf0` (light gray). This overrides the dark gradient set in `main.css` via `@layer base`.

**Mechanism:**
1. `main.css` sets `html, body, #app { background: linear-gradient(135deg, #121B26 0%, #0F1720 100%); }`
2. But `App.vue` renders `<div class="app-shell">` inside `#app`
3. The plain CSS in `App.vue` has `background-color: #e8eaf0` which overrides the parent gradient
4. Tailwind CSS IS working (verified in built CSS), but the component-level plain CSS overrides it

## Evidence

- timestamp: 2026-04-13
  checked: electron/dist/assets/index-3IXSiyp2.css (built CSS output)
  found: Dark theme tokens ARE present - glass-surface, glass-btn, glass-input classes, dark gradient (#121b26, #0f1720), custom colors (app, surface, text-primary, text-muted, accent-*)
  implication: Tailwind IS compiling correctly

- timestamp: 2026-04-13
  checked: electron/src/renderer/App.vue
  found: `<style>` block with `.app-shell { background-color: #e8eaf0; }`
  implication: Plain CSS overrides Tailwind dark theme

## Resolution

root_cause: App.vue has plain CSS `.app-shell { background-color: #e8eaf0; }` which overrides the dark gradient from main.css
fix: Changed App.vue to use `background: linear-gradient(135deg, #121B26 0%, #0F1720 100%);` instead of `background-color: #e8eaf0`
verification: User needs to restart dev server and verify dark theme displays
files_changed: ['electron/src/renderer/App.vue']
