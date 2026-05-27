## Summary

<!-- What does this PR do? One or two sentences. -->

## Type of change

<!-- Choose one — this drives the version bump on merge. -->

- [ ] `fix: ...` — bug fix → patch bump (0.0.**x**)
- [ ] `feat: ...` — new feature → minor bump (0.**x**.0)
- [ ] `feat!: ...` / `BREAKING CHANGE` — breaking change → major bump (**x**.0.0)
- [ ] `chore:` / `docs:` / `ci:` / `refactor:` — no release created

## PR title format

Your PR title becomes the commit message on merge and determines the version bump:

```
feat(resume): add cover letter section
fix: pdf export crash on empty work history
feat!: replace /generate endpoint with /build (breaking)
chore: update dev dependencies
```

Pattern: `type(optional-scope): short description in lowercase`

## Checklist

- [ ] Tests added / updated under `backend/tests/` for any changed `backend/app/` code
- [ ] `pytest` passes locally (`cd backend && pytest`)
- [ ] PR title follows the format above
