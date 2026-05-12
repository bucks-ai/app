# Handoff: feature/blueprint-api

## Summary

Replaced the frontend-only mock blueprint generator with a real server-side AI blueprint generation route.

## Files Created

- `src/app/api/generate-blueprint/route.ts` — POST handler; validates required fields, calls OpenAI gpt-4o with structured JSON output, returns `BusinessBlueprint` or a typed error.
- `src/lib/blueprint-prompt.ts` — Server-side prompt builder that positions bucks.ai as an autonomous startup operator and requests a structured JSON blueprint from the model.
- `HANDOFF_blueprint-api.md` — this file.

## Files Modified

- `src/components/intake/IdeaIntakeWizard.tsx` — Added real `handleGenerateBlueprint` flow: calls `/api/generate-blueprint`, handles `missing_api_key` (503), generic errors, loading state, and the explicit "Use demo blueprint" fallback. Mock data is never used silently.
- `package.json` / `package-lock.json` — Added `openai ^6.37.0`.

## Dependencies Installed

```
openai@^6.37.0
```

## Commands Run

```bash
npm install
npm run lint
npm run build
```

## Lint / Build Status

- `npm run lint` — **passed** (no errors or warnings)
- `npm run build` — **passed** (TypeScript clean, all routes compiled)

## How to Test Locally

1. Copy `.env.example` to `.env.local` and add a real OpenAI key:
   ```
   OPENAI_API_KEY=sk-...
   ```
2. Start the dev server:
   ```bash
   npm run dev
   ```
3. Open [http://localhost:3000/intake](http://localhost:3000/intake).
4. Complete all four wizard steps and click **Generate Blueprint**.
5. Observe a real AI-generated blueprint in the `BlueprintPreview` component.

**Without a key:** The wizard shows an amber banner with setup instructions and a "Use demo blueprint" button. No silent fallback occurs.

## Required .env.local Values

```
OPENAI_API_KEY=sk-...
```

All other keys in `.env.example` are unused by this feature.

## What Works Now

- `/api/generate-blueprint` POST route — real AI blueprint generation via gpt-4o
- Structured JSON output enforced at the model level (`response_format: json_object`)
- Typed 400 validation errors for missing required fields
- Typed 503 error when `OPENAI_API_KEY` is absent
- Typed 500 error when OpenAI call or JSON parse fails
- Loading state: "bucks.ai is building your launch blueprint…" with spinner
- Missing-key banner with setup instructions and explicit demo fallback
- Error banner with retry + demo fallback buttons
- Demo blueprint fallback only accessible via explicit button click

## Blockers

None. The feature is complete and building cleanly.

## Recommended Next Task

**Connect the blueprint to an agent handoff system.** The `BusinessBlueprint` is now returned to the client but only displayed statically. The natural next step is to persist it (Supabase) and hand it off to the first autonomous bucks.ai agent (e.g. the stack builder or GTM outreach agent). This would make the "next autonomous actions" section actionable rather than decorative.
