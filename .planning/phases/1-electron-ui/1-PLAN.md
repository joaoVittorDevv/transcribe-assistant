# Phase 1 — Electron UI Foundation: Gap Closure

## SitUATION

Phase 1 UAT found 3 functional bugs. Additionally, the implementation uses a **light neomorphic** design (per DESIGN.md's "Silk — Extruded Light" theme) but the authoritative mockup `screen.png` shows a **dark glassmorphism** design with deep navy backgrounds, translucent surfaces with backdrop-blur, and vibrant accents. The current screenshot (`Imagem_colada.png`) correctly reflects the light neomorphic code — but the code does NOT match the mockup the user wants.

## Challenge

Fix the 3 UAT bugs AND migrate the visual design from light neomorphic to dark glassmorphism to match `screen.png`.

## Design Target: Dark Glassmorphism (from screen.png)

### Color Palette
- **Background:** Deep navy/charcoal gradient `#121B26 → #0F1720` (not the current `#e8eaf0`)
- **Sidebar surface:** Translucent `rgba(20, 32, 48, 0.6)` with `backdrop-filter: blur(16px)`
- **Text primary:** `#E0E0E0` (off-white)
- **Text secondary/muted:** `#828282`
- **Online/Success green:** `#27AE60` (current has this — keep)
- **Record/Action red:** `#EB5757` (current has this — keep)
- **Active/focus blue glow:** Electric blue `ring-2 ring-[#3B82F6]/50` on focused editor
- **Tab active indicator:** Electric blue underline

### Typography
- Font: Plus Jakarta Sans (already installed) — matches the clean sans-serif in mockup
- Weights: medium (500) for body, semibold (600) for headings

### Sidebar (CRITICAL FIX — UAT Issue 1)
- Unified translucent glass panel on the left ~20% width
- NOT floating cards — items inside a single container
- Translucent background with backdrop-blur
- Active item highlighted with subtle gradient + white checkmark icon
- "Gerenciar Prompts" button at bottom of the same glass panel

### Shadows vs Glass
- Remove ALL `shadow-neo-raised` / `shadow-neo-inset` neomorphic utilities
- Add glass utilities: `backdrop-blur`, `bg-black/` alpha layers, `border border-white/10` for rim-light effect
- Raised cards replaced with translucent glass surfaces
- Editor area: inset look via border + subtle inner glow, not shadow-inset

### Border Radius
- Containers: `rounded-2xl` (16px)
- Buttons/cards: `rounded-xl` (12px)
- Tabs: `rounded-lg` (8px)

## Tasks

### Task G1: Dark Theme Base — Tailwind Config + CSS
**Files:** `tailwind.config.js`, `src/renderer/styles/main.css`

Action:
1. Replace `neo-bg: '#e8eaf0'` with dark palette tokens:
   - `bg-app: '#121B26'`
   - `bg-surface: 'rgba(20, 32, 48, 0.6)'`
   - `text-primary: '#E0E0E0'`
   - `text-muted: '#828282'`
   - `accent-green: '#27AE60'`
   - `accent-red: '#EB5757'`
   - `accent-blue: '#3B82F6'`
2. Replace `shadow-neo-raised` / `shadow-neo-inset` with glass utilities in `main.css`
3. Update body background to gradient `#121B26 → #0F1720`
4. Add `.glass-surface` utility class: `bg-surface backdrop-blur-md border border-white/10 rounded-2xl`

**Verify:** Background changes from light gray to dark navy on app restart.

---

### Task G2: Sidebar — Unified Glass Panel (UAT Issue 1 fix)
**Files:** `src/renderer/components/layout/Sidebar.vue`

Action:
1. Remove the outer `<aside>` padding and give it `width: 20%`, `min-width: 200px`, `height: 100%`
2. Add a single `.glass-surface` div wrapping ALL sidebar content (prompt header, item list, manage button)
3. The glass panel fills the full sidebar height, items distributed with `flex-col justify-between`
4. Prompt items (`Resumos do dia`, `Projetos Gerais`) become simple list items inside the glass panel — not separate floating cards
5. Active item highlighted with `bg-accent-blue/20 border-l-2 border-accent-blue`
6. "Gerenciar Prompts" button at bottom of the glass panel

**Verify:** Sidebar is one unified translucent panel. No floating independent containers. Items aligned inside it.

---

### Task G3: Quill Toolbar — Fix H1/H2/H3/Lists/Alignment (UAT Issue 2)
**Files:** `src/renderer/components/editor/TextEditor.vue`, `EditorToolbar.vue`, `ToolbarBtn.vue`

Action:
1. In `TextEditor.vue`, fix `handleFormat` — Quill's `format()` API:
   - For `header`, pass number value correctly: `quill.format('header', value)` where value is 1|2|3
   - For `list`, pass `'bullet'` or `'ordered'`
   - For `align`, pass `'left'`, `'center'`, `'right'`
   - `quill.format(type, value)` — second arg MUST be the value, not boolean
2. In `EditorToolbar.vue`, ensure `heading(level)` emits `['header', level]`, `list(type)` emits `['list', type]`
3. Fix `ToolbarBtn.vue` — add `type="button"` to prevent form submission

**Verify:** H1 makes text larger, H2 medium, H3 small. Bullet list creates list items. Alignment buttons center/left/right text.

---

### Task G4: Reset Button — Wire to Quill (UAT Issue 3)
**Files:** `src/renderer/components/bottom/BottomActionBar.vue`, `src/renderer/composables/useTabs.ts`

Action:
1. In `BottomActionBar.vue`, `resetActiveTab()` currently only clears `useTabs` state — it must also clear the Quill editor
2. Expose a `clearEditor()` function from `TextEditor.vue` via `defineExpose({ clearEditor })`
3. In `BottomActionBar.vue`, get a ref to `TextEditor` component and call `clearEditor()` + `resetActiveTab()`
4. Quill clearing: call `quill.setText('')` on the instance

**Verify:** Type text, click Reset, editor is empty.

---

### Task G5: Global Style Audit — Match Mockup
**Files:** All `.vue` components, `main.css`

Action:
1. Remove all `neo-bg`, `neo-primary`, `neo-tertiary`, `shadow-neo-*` classes from all components
2. Replace with dark glass equivalents:
   - Cards: `.glass-surface`
   - Buttons: `bg-surface/80 backdrop-blur-sm border border-white/10 rounded-xl text-text-primary`
   - Active states: `ring-2 ring-accent-blue/50`
   - Inactive: slightly lower opacity
3. Editor area: `bg-surface/40 backdrop-blur-sm border border-white/10 rounded-xl focus-within:ring-2 focus-within:ring-accent-blue/50`
4. Top bar: translucent glass strip `bg-surface/60 backdrop-blur-md`
5. Bottom bar: same glass treatment
6. Ensure `bg-app` gradient fills the full viewport

**Verify:** App visually matches the dark glassmorphism style of `screen.png`.

---

### Task G6: TypeScript + Build Check
**Files:** `tsconfig.json`, `vite.*.config.ts`

Action:
1. Run `npx vue-tsc --noEmit` — must be zero errors
2. Run `npx vite build --config vite.renderer.config.ts` — must succeed
3. Run `make run-electron` — app launches with dark theme

**Verify:** All three pass.

---

## Verification Criteria

1. Dark glassmorphism design matches `screen.png` (dark navy background, translucent surfaces, vibrant accents)
2. Sidebar is a single unified glass panel — no floating independent containers
3. Quill toolbar: H1/H2/H3, bullet list, numbered list, alignment all work correctly
4. Reset button clears editor content
5. `vue-tsc --noEmit` → zero errors
6. `make run-electron` → dark-themed window opens
7. All 3 UAT issues confirmed fixed
