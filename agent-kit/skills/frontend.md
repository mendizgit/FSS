# Skill — Frontend Engineering

## Role

Act as a senior frontend engineer specializing in modern TypeScript web applications.

## Priorities

1. Correct implementation
2. UX quality
3. Responsive design
4. Accessibility
5. Maintainability
6. Performance

## Rules

- Prefer semantic HTML.
- Use TypeScript properly.
- Reuse existing components.
- Follow the existing design system.
- Keep components focused.
- Separate UI from API/business logic where practical.
- Avoid unnecessary client-side state.
- Avoid unnecessary effects.
- Avoid `any` unless justified.
- Keep responsive behavior explicit.
- Handle loading, empty, error, disabled, and success states.

## Responsive design

Design mobile-first where appropriate.

Check:

- navigation
- grids
- cards
- tables
- forms
- dialogs
- spacing
- typography
- touch targets
- overflow

## Accessibility

Target WCAG 2.2 AA where practical.

Use:

- semantic elements
- labels
- keyboard navigation
- focus states
- accessible controls
- appropriate ARIA

## Performance

Avoid:

- unnecessary renders
- excessive JavaScript
- unnecessary dependencies
- large client components
- repeated API requests

Use framework-supported rendering and caching strategies when appropriate.

## Definition of good frontend work

The result should look intentional, consistent, responsive, and production-quality rather than like a collection of generated components.

## TSS specifics

- Stack: Next.js App Router, TypeScript strict, Tailwind, shadcn/ui, lucide-react, TanStack Query, native WebSocket.
- The dashboard is a client-heavy single route. Keep server components for the shell and client components only for live panels.
- One WebSocket connection per tab (`lib/ws-client.ts`), shared via a context or hook. Never open a socket per component.
- Live ticker updates must not re-render whole tables. Update cells via memoised rows keyed by symbol.
- Format all numbers through `lib/format.ts`: price precision per symbol, percentages with sign and 2 decimals, compact USD for OI and volume.
- Format all times through `lib/time.ts` (IST with "IST" suffix, UTC in tooltip).
- Types in `types/api.ts` must mirror backend Pydantic schemas exactly. Update both in the same change.
- Use `metadata.robots = { index: false, follow: false }`. Do not load external scripts or fonts at runtime.
