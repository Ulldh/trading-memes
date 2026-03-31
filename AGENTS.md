# Coding Standards — Gentleman Programming Protocol

## 0. Review Scope (CRITICAL — read first)

- **Only flag violations in NEW or MODIFIED code.** Pre-existing code is out of scope.
- If a file was partially modified, only review the changed/added lines and their immediate context.
- Do NOT flag violations in unchanged lines, even if they break rules below.
- Next.js App Router pages (`app/**/page.tsx`, `app/**/layout.tsx`) REQUIRE `export default` — this is a framework constraint, not a violation.
- Next.js pages may mix logic and UI in a single file — this is acceptable for page-level components.

## 1. Architecture (Scope Rule — absolute, no exceptions)

### Scope Rule
- Code used in 2+ places → MUST go in global/shared directories
- Code used in 1 place → MUST stay local to its feature
- "Might be reused later" is NOT shared. Only proven reuse counts.
- Creating `domain/` folders is explicitly prohibited (breaks traceability)

### Scream Architecture
- Folder names describe WHAT the app does, not the technology
- Correct: `features/checkout`, `features/user-authentication`
- Wrong: `features/forms`, `features/models`, `features/hooks`

### Container-Presenter Pattern
- Containers: smart components (business logic, state, API calls). No UI decisions.
- Presenters: dumb components (receive props, render UI). No store access, no side effects.
- Container filename = feature name

## 2. TypeScript

- `strict: true` enabled, no `any` type anywhere
- Use `interface` for object shapes, `type` for unions/intersections
- All functions must have explicit return types
- Prefer `unknown` over `any` for untyped external data
- Use `as const` for literal objects and enums
- No type assertions (`as`) unless absolutely necessary — prefer type narrowing

## 3. React

- React 19+: Do NOT use `useMemo`, `useCallback`, or `React.memo` (React Compiler handles memoization)
- Named exports only — no `export default` (EXCEPTION: Next.js pages/layouts require `export default`)
- Props interface naming: `[ComponentName]Props`
- One component per file
- Custom hooks: always use `use` prefix (`useTaskStore`, `useAuth`)
- No prop drilling beyond 1 level — use stores or context

## 4. Styling (Tailwind CSS)

- Use Tailwind utility classes directly in JSX
- Use `cn()` helper (clsx + tailwind-merge) for conditional classes
- No inline `style={}` attributes
- No CSS modules or styled-components
- Color contrast minimum 4.5:1 (WCAG AA). Use `text-gray-500` or darker on white backgrounds.

## 5. Validation

- All user input MUST be validated with Zod schemas before processing
- Use `safeParse()`, never `parse()` (handle errors gracefully)
- Zod 4: use `.issues` not `.errors` for error access
- Apply `.trim()` on string schemas to prevent whitespace-only inputs
- Validated data (`result.data`) is what gets passed forward, not raw input

## 6. State Management (Zustand)

- Global state: `src/stores/` for data shared across 2+ features
- Local state: `src/features/[feature]/stores/` for feature-specific state
- Store actions own business logic (ID generation, defaults, transformations)
- Components select only what they need: `useStore((state) => state.specificField)`

## 7. Security (OWASP)

- NEVER use `dangerouslySetInnerHTML`
- NEVER use `eval()`, `Function()`, `document.write()`, or `innerHTML`
- No hardcoded secrets, API keys, or tokens in source code
- Sanitize all user inputs at system boundaries
- Use `crypto.randomUUID()` for IDs — no sequential or predictable identifiers
- Validate data read from localStorage/external sources (treat as untrusted)

## 8. Accessibility (WCAG 2.1 AA)

- All interactive elements must be keyboard accessible
- Visible focus indicators on every focusable element (`focus-visible` styles)
- Use semantic HTML: `<main>`, `<nav>`, `<section>`, `<button>`, `<ul>`/`<li>`
- Images require `alt` text
- Forms: use `<label htmlFor>`, `aria-invalid`, `aria-describedby` for errors
- Modals: trap focus, close on Escape, return focus on close
- Live regions (`aria-live="polite"`) for dynamic status changes
- No color as the only means of conveying information

## 9. Testing

- Co-locate test files with source: `Component.test.tsx` next to `Component.tsx`
- Test behavior, not implementation details
- Use React Testing Library: `render`, `screen`, `userEvent`
- Arrange-Act-Assert pattern in every test
- Descriptive test names: `it('should display error when title is empty')`
- Test the user experience: what the user sees and does, not internal state

## 10. Git

- Conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`
- Branch naming: `feature/[name]`, `fix/[name]`, `refactor/[name]`
- PR required before merge to main
- Each commit should be a single logical change
