<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Standard command workflow

- After editing code, run `./scripts/check.sh`
- To finish a feature branch, run `./scripts/finish-feature.sh "message"`
- To merge into main, run `./scripts/merge-feature.sh feature/name`
- Never commit `.env.local`
- Never print secrets
- Never run `npm audit fix --force`
- Never use `git push --force`
- Prefer `git merge --no-edit` to avoid vim merge screens
- If conflicts appear, stop and report them
