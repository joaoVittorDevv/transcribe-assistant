# Phase 1: Electron UI Foundation

## Situation

The transcribe-assistant project currently runs as a Python desktop app with Flet and CustomTkinter UIs. A new Electron-based UI is being introduced to provide cross-platform desktop packaging with a modern web stack (Vue 3 + Tailwind + TypeScript). Phase 1 establishes the complete visual foundation with all UI components rendered, state management wired, and a mocked transcription flow -- no real audio or transcription logic yet.

## Challenge

Build a fully functional Electron shell with:
- Neomorphic "Extruded Light" design system implemented as Tailwind custom utilities
- Tab management with independent per-tab text state
- Transcription state machine (IDLE/RECORDING/TRANSCRIBING) with a single button cycling through states
- Conditional cancel button (only visible during RECORDING and TRANSCRIBING)
- All controls functional in their mocked form: copy, reset, file upload, audio source toggle, provider dropdown
- i18n structure ready for future translations
- Working `make run-electron` command

## Approach

### Technology Choices
- **Bundler:** Electron Forge with Vite + TypeScript template (produces working `npm run make` and `npm run start`)
- **Framework:** Vue 3 Composition API (script setup)
- **Styling:** Tailwind CSS v3 with custom neomorphic utilities matching the exact design tokens from DESIGN.md
- **Editor:** QuillJS via `@quailjs/vue` or direct Quill integration
- **State:** Vue `reactive`/`ref` composables (no Pinia needed for Phase 1)
- **Build:** TypeScript strict mode

### Design System Implementation (Tailwind Custom Utilities)
Add to `tailwind.config.js`:
- `neo-raised`: `{ boxShadow: '6px 6px 12px rgba(0,0,0,0.08), -6px -6px 12px rgba(255,255,255,0.6)' }`
- `neo-inset`: `{ boxShadow: 'inset 4px 4px 8px rgba(0,0,0,0.06), inset -4px -4px 8px rgba(255,255,255,0.5)' }`
- `neo-bg`: `{ backgroundColor: '#e8eaf0' }`
- `neo-primary`: text color `#6366f1`
- `neo-tertiary`: text color `#7c3aed`
- `border-radius`: minimum `12px` enforced via `rounded-xl` (or `rounded-2xl`)
- Never combine raised with borders or gradients

### File Structure
```
electron/
├── src/
│   ├── main/              # Electron main process
│   │   └── index.ts
│   ├── preload/           # Preload script (IPC bridge)
│   │   └── index.ts
│   └── renderer/          # Vue 3 renderer
│       ├── App.vue
│       ├── main.ts
│       ├── components/
│       │   ├── layout/
│       │   │   ├── Sidebar.vue
│       │   │   └── MainWorkspace.vue
│       │   ├── topbar/
│       │   │   ├── ProviderToggle.vue
│       │   │   ├── NetworkStatus.vue
│       │   │   ├── LanguageToggle.vue
│       │   │   └── TopActionButtons.vue
│       │   ├── tabs/
│       │   │   ├── TabBar.vue
│       │   │   └── TabItem.vue
│       │   ├── editor/
│       │   │   ├── TextEditor.vue        # QuillJS wrapper
│       │   │   └── EditorToolbar.vue     # Bold, Italic, Code, etc.
│       │   └── bottom/
│       │       ├── Timer.vue
│       │       ├── AudioVisualizer.vue  # Mock waveform bars
│       │       ├── RecordButton.vue     # State machine button
│       │       ├── CancelButton.vue     # Conditional visibility
│       │       └── BottomActionBar.vue
│       ├── composables/
│       │   ├── useTranscriptionState.ts  # IDLE/RECORDING/TRANSCRIBING
│       │   ├── useTabs.ts                 # Tab management
│       │   └── useClipboard.ts
│       ├── i18n/
│       │   ├── index.ts
│       │   ├── en.json
│       │   └── pt.json
│       └── styles/
│           └── main.css        # Tailwind directives + font import
├── index.html
├── package.json
├── forge.config.ts
├── vite.main.config.ts
├── vite.preload.config.ts
├── vite.renderer.config.ts     # Vue plugin + Tailwind
├── tsconfig.json
├── tailwind.config.js
├── postcss.config.js
└── Makefile                     # `make run-electron` → npm run start
```

## Tasks

### Task 1: Electron Forge Scaffold
**Files created:**
- `electron/package.json` -- Electron Forge with Vite + TypeScript, Vue 3 as dev dep
- `electron/forge.config.ts` -- Electron Forge config
- `electron/vite.main.config.ts`, `vite.preload.config.ts`, `vite.renderer.config.ts` -- Vite configs
- `electron/tsconfig.json` -- TypeScript strict mode config
- `electron/index.html` -- HTML entry point

**Action:** Initialize Electron Forge using the official Vite template (`npm create electron-app@latest -- --template=vite-typescript`). Then install Vue 3 (`npm install vue@^3.5 @types/node`) and add Vue plugin to `vite.renderer.config.ts` (`import vue from '@vitejs/plugin-vue'`). Register Vue plugin in the renderer config. Set `nodeIntegration: false` and `contextIsolation: true` in `forge.config.ts` webPreferences.

**Verify:** `npm run start` in `electron/` opens an Electron window with the default Vite page.

---

### Task 2: Tailwind + Neomorphic Design System
**Files created:**
- `electron/tailwind.config.js` -- Custom neomorphic utilities matching DESIGN.md tokens
- `electron/postcss.config.js` -- PostCSS with Tailwind
- `electron/src/renderer/styles/main.css` -- Tailwind directives + Plus Jakarta Sans `@import`

**Action:** Install Tailwind (`npm install -D tailwindcss postcss autoprefixer`). Configure `tailwind.config.js` with:
```js
colors: {
  'neo-bg': '#e8eaf0',
  'neo-primary': '#6366f1',
  'neo-tertiary': '#7c3aed',
},
boxShadow: {
  'neo-raised': '6px 6px 12px rgba(0,0,0,0.08), -6px -6px 12px rgba(255,255,255,0.6)',
  'neo-inset': 'inset 4px 4px 8px rgba(0,0,0,0.06), inset -4px -4px 8px rgba(255,255,255,0.5)',
},
borderRadius: { 'neo': '12px' },
fontFamily: { 'plus-jakarta': ['Plus Jakarta Sans', 'sans-serif'] },
```
In `main.css`:
```css
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600&display=swap');
@tailwind base;
@tailwind components;
@tailwind utilities;
```

**Verify:** A test Vue component with class `neo-bg shadow-neo-raised rounded-neo` renders the correct neomorphic background and shadow.

---

### Task 3: i18n Structure
**Files created:**
- `electron/src/renderer/i18n/index.ts` -- i18n composable (simple reactive object, no vue-i18n dependency)
- `electron/src/renderer/i18n/en.json`
- `electron/src/renderer/i18n/pt.json`

**Action:** Create a minimal i18n composable:
```ts
// electron/src/renderer/i18n/index.ts
import { reactive } from 'vue';
import en from './en.json';
import pt from './pt.json';

const messages = { en, pt };
const state = reactive({ locale: 'pt', messages: messages['pt'] });

export function t(key: string) {
  return state.messages[key] ?? key;
}

export function setLocale(locale: 'en' | 'pt') {
  state.locale = locale;
  state.messages = messages[locale];
}
```
Add keys for: `sidebar.title`, `sidebar.manage_prompts`, `tabs.new_tab`, `tabs.close_tab`, `status.idle`, `status.recording`, `status.transcribing`, `status.cancel`, `buttons.copy`, `buttons.reset`, `buttons.import_audio`, `provider.auto`, `provider.google`, `provider.whisper`, `network.online`, `network.offline`, `language.pt`, `language.en`.

**Verify:** `setLocale('en')` and calling `t('sidebar.title')` returns the English string.

---

### Task 4: Tab Management Composable
**Files created:**
- `electron/src/renderer/composables/useTabs.ts`

**Action:** Implement a `useTabs()` composable:
```ts
import { reactive, ref } from 'vue';
export interface Tab { id: string; title: string; content: string; }
const tabs = reactive<Tab[]>([{ id: '1', title: 'Tab 1', content: '' }]);
const activeTabId = ref('1');

export function useTabs() {
  function addTab() { tabs.push({ id: Date.now().toString(), title: `Tab ${tabs.length + 1}`, content: '' }); }
  function closeTab(id: string) { const i = tabs.findIndex(t => t.id === id); if (i > -1) tabs.splice(i, 1); }
  function setActive(id: string) { activeTabId.value = id; }
  function updateContent(id: string, content: string) { const tab = tabs.find(t => t.id === id); if (tab) tab.content = content; }
  return { tabs, activeTabId, addTab, closeTab, setActive, updateContent };
}
```

**Verify:** `addTab()` creates a new tab object, `closeTab(id)` removes it, `updateContent(id, 'text')` persists content independently per tab.

---

### Task 5: Transcription State Machine Composable
**Files created:**
- `electron/src/renderer/composables/useTranscriptionState.ts`

**Action:** Implement a `useTranscriptionState()` composable with states `IDLE`, `RECORDING`, `TRANSCRIBING`. The record button click handler cycles:
- IDLE -> RECORDING (start timer, show visualizer bars animated)
- RECORDING -> TRANSCRIBING (stop timer, show "transcribing..." state)
- TRANSCRIBING -> IDLE (insert mock text into active tab editor, reset timer)

Cancel button visibility: computed property returns `true` only when state is `RECORDING` or `TRANSCRIBING`. Cancel click returns to `IDLE` and resets timer.

Mock text insertion: on TRANSCRIBING->IDLE transition, insert 2-3 sentences of Portuguese lorem ipsum into the active tab via `updateContent(activeTabId.value, mockText)`.

**Verify:** State cycles correctly. Cancel button hidden in IDLE, visible in RECORDING and TRANSCRIBING. After TRANSCRIBING completes, mock text appears in the editor.

---

### Task 6: Sidebar Component
**Files created:**
- `electron/src/renderer/components/layout/Sidebar.vue`

**Action:** Layout:
- Top: microphone icon (heroicons outline) + "Prompt Ativo" label (neo-bg, neo-raised, rounded-xl, p-4)
- Middle: list with two static items "Resumos do dia" and "Projetos Gerais" (neo-bg rounded-lg p-3, cursor-pointer hover:shadow-neo-inset)
- Bottom: "Gerenciar Prompts" button (neo-bg shadow-neo-raised rounded-xl p-3, full width, text-neo-primary font-semibold)
- Width: `w-[20%]`, min-width `200px`

**Verify:** Sidebar renders with all three sections. Width is approximately 20% of the window.

---

### Task 7: Top Utility Bar Components
**Files created:**
- `electron/src/renderer/components/topbar/ProviderToggle.vue`
- `electron/src/renderer/components/topbar/NetworkStatus.vue`
- `electron/src/renderer/components/topbar/LanguageToggle.vue`
- `electron/src/renderer/components/topbar/TopActionButtons.vue`

**Action:** `ProviderToggle` -- Three-button toggle group (Automático / Google / Whisper). Selected state uses `neo-bg shadow-neo-inset rounded-lg`. Unselected uses `neo-bg shadow-neo-raised rounded-lg`. `NetworkStatus` -- Green/yellow dot indicator + "Online"/"Offline" label. Static green for Phase 1 (mocked). `LanguageToggle` -- Two buttons PT | EN. Active language uses `neo-bg shadow-neo-inset`. `TopActionButtons` -- Copy button (copies active tab content to clipboard) + Historico button. Both neo-raised rounded-xl.

**Verify:** All four components render in a horizontal bar. Provider toggle shows correct active/inactive styling. Language toggle calls `setLocale()`.

---

### Task 8: Tab Bar Component
**Files created:**
- `electron/src/renderer/components/tabs/TabBar.vue`
- `electron/src/renderer/components/tabs/TabItem.vue`

**Action:** `TabBar` renders a horizontal scrollable list of `TabItem` components plus a `+` add button at the end. `TabItem` shows tab title + close (x) button. Active tab: `neo-bg shadow-neo-inset`. Inactive: `neo-bg shadow-neo-raised`. Click on tab activates it. Click on x closes the tab (if more than one tab exists). `+` button calls `addTab()`.

**Verify:** Clicking a tab sets it active (visual change). Clicking `x` removes the tab. Clicking `+` adds a new tab. Closing all tabs leaves at least one tab remaining.

---

### Task 9: QuillJS Text Editor with Toolbar
**Files created:**
- `electron/src/renderer/components/editor/TextEditor.vue`
- `electron/src/renderer/components/editor/EditorToolbar.vue`

**Action:** `EditorToolbar` buttons: Bold, Italic, Code (inline code), Strikethrough, H1, H2, H3, Bullet List, Numbered List, Align Left, Align Center, Link. Each button is a `neo-bg shadow-neo-raised rounded-lg` icon button. Active state uses `neo-bg shadow-neo-inset`. `TextEditor` wraps QuillJS instance in a `neo-bg rounded-xl p-4` container with `shadow-neo-inset` border (editor area appears carved into the surface). Neon-blue glowing border effect on focus: `focus-within:ring-2 focus-within:ring-[#6366f1]/50`. Connect toolbar buttons to Quill `format()` API.

**Verify:** Quill editor renders. Typing text works. Toolbar buttons apply formatting (bold makes text bold, H1 changes size, etc.). Focus state shows indigo glow.

---

### Task 10: Bottom Control Bar Components
**Files created:**
- `electron/src/renderer/components/bottom/Timer.vue`
- `electron/src/renderer/components/bottom/AudioVisualizer.vue`
- `electron/src/renderer/components/bottom/RecordButton.vue`
- `electron/src/renderer/components/bottom/CancelButton.vue`
- `electron/src/renderer/components/bottom/BottomActionBar.vue`

**Action:** `Timer` -- Displays `MM:SS` format, neo-bg rounded-lg. `AudioVisualizer` -- 8-10 vertical bars representing audio levels. Bars are neo-primary colored, height animated with CSS transitions. Static low-level animation in IDLE. `RecordButton` -- Large circular button (80px diameter), `neo-bg shadow-neo-raised rounded-full`. Red circle icon in center. On click, calls the state machine handler from `useTranscriptionState`. `CancelButton` -- `neo-bg shadow-neo-raised rounded-xl` button with `X` or "Cancelar" label. `visible` computed from `useTranscriptionState`. Hidden with `v-show="false"` in IDLE. `BottomActionBar` -- Horizontal layout: Timer (left) + Visualizer (center-left) + RecordButton (center) + CancelButton (right of record) + Copy button + Reset button.

**Verify:** Timer counts up in RECORDING state. Visualizer bars animate during RECORDING. Record button cycles state machine. Cancel button appears/disappears correctly. Copy copies active tab content. Reset clears active tab content.

---

### Task 11: MainWorkspace Layout and App Assembly
**Files created:**
- `electron/src/renderer/components/layout/MainWorkspace.vue`
- `electron/src/renderer/App.vue`

**Action:** `MainWorkspace` composes: Top Utility Bar (ProviderToggle, NetworkStatus, LanguageToggle, TopActionButtons) -> Tab Bar -> Text Editor (with toolbar) -> Bottom Control Bar. All in a `flex flex-col h-full` layout filling the right 80% of the screen. `App.vue` composes: `Sidebar` (left, 20%) + `MainWorkspace` (right, 80%) in a horizontal flex row, both with `neo-bg` background. Import and wire all composables (`useTabs`, `useTranscriptionState`). The `+` and `x` buttons on tabs call `addTab()`/`closeTab()` from `useTabs`. Record button calls state machine handler. Copy/Reset call clipboard and clear functions. Provider dropdown, audio source toggle, and file upload button are rendered but non-functional in Phase 1 (their state is stored but has no effect).

**Verify:** `make run-electron` (or `npm run start` in electron/ directory) opens the full application window with the complete neomorphic UI: sidebar on left, all four workspace layers visible, all tabs functional, record button cycling states, cancel button appearing/disappearing, copy/reset working.

---

### Task 12: Makefile Entry Point
**Files created:**
- `electron/Makefile`

**Action:** Add to the project `Makefile` (at root, alongside existing entries):
```make
run-electron:
	cd electron && npm install && npm run start
```
This installs electron dependencies and launches the app.

**Verify:** `make run-electron` at project root opens the Electron window.

---

## Verification Criteria

1. `make run-electron` successfully opens an Electron window without errors
2. All UI elements render with correct neomorphic styling (raised/inset shadows, correct colors, 12px+ border-radius)
3. Tab management: add, close, switch, and independent per-tab content all work
4. Transcription state machine: single button cycles IDLE -> RECORDING -> TRANSCRIBING -> IDLE correctly
5. Cancel button visible only during RECORDING and TRANSCRIBING states
6. Copy button copies active tab content to clipboard
7. Reset button clears active tab content
8. Language toggle switches between PT and EN labels
9. QuillJS editor accepts text input and toolbar formatting works
10. Timer counts up during RECORDING state
11. Audio visualizer bars animate during RECORDING state
12. Provider dropdown, audio source toggle, and file upload button render (no-op for Phase 1)
13. Electron security: Context Isolation is `true`, Node Integration is `false`
14. TypeScript strict mode produces zero errors

## Success Checklist

- [ ] Electron Forge + Vite + Vue 3 scaffold builds and runs
- [ ] Tailwind configured with neomorphic custom utilities
- [ ] Plus Jakarta Sans font loaded via Google Fonts import
- [ ] i18n composable with PT/EN JSON files, `setLocale()` functional
- [ ] `useTabs()` composable: add, close, switch, independent content
- [ ] `useTranscriptionState()` composable: IDLE/RECORDING/TRANSCRIBING cycle, cancel visibility
- [ ] `useClipboard()` composable: copy to clipboard functional
- [ ] Sidebar renders with microphone icon, prompt list, manage prompts button
- [ ] Top bar: Provider toggle, network status, language toggle, copy/historico buttons
- [ ] Tab bar with add/close functionality
- [ ] QuillJS text editor with full toolbar formatting
- [ ] Bottom bar: timer, audio visualizer, record button, cancel button, copy, reset
- [ ] Provider dropdown, audio source toggle, file upload button rendered (mocked)
- [ ] `make run-electron` opens fully rendered UI
- [ ] Context Isolation enabled, Node Integration disabled
- [ ] TypeScript strict mode clean
