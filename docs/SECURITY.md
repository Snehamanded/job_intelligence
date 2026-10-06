# Security

This covers what is implemented through Phase 2. AI-specific safety (prompt injection, consent,
budget, truthfulness) is detailed in [AI.md](AI.md).

## Authentication

- **Passwords** are hashed with argon2id (`argon2-cffi` defaults). Minimum 8 characters, maximum 128.
- **Login** returns the same error for an unknown email and a wrong password. For an unknown
  email it still verifies against a dummy hash, so response timing does not reveal which emails
  exist.
- **Sessions** are a JWT (HS256, signed with `JWT_SECRET`, claims `sub`, `iat`, `exp`,
  `type=access`). It is stored in the `access_token` cookie:
  `HttpOnly; SameSite=Lax; Path=/`, plus `Secure` when `COOKIE_SECURE=true`. JavaScript never sees it.
- **Lifetime** is `ACCESS_TOKEN_TTL_MINUTES` (default 24 h). There is no refresh token. Users sign
  in again after expiry.
- **Logout** clears the cookies. JWTs are stateless, so a stolen token stays valid until it
  expires. A server-side session or token version can be added if that matters later.
- **Registration** can be turned off with `ALLOW_REGISTRATION=false`. The MVP is single-user.

## CSRF

SameSite=Lax already blocks cross-site POSTs carrying the session cookie. On top of that, every
mutating request (`POST`/`PUT`/`PATCH`/`DELETE` under `/api`) must pass a double-submit check:

1. The API stores a random token in the `csrf_token` cookie (`HttpOnly`, `SameSite=Lax`).
2. The web app receives the same token in a JSON body (`GET /api/auth/csrf`, or the
   login/register response) and keeps it in memory only.
3. The request must send it back in the `X-CSRF-Token` header. The API compares it to the cookie
   in constant time and returns `403` on a mismatch.

Another origin cannot read the response body (CORS), so it cannot learn the token. The token is
rotated on login and register, and cleared on logout. The check is a router-level dependency,
so new mutating routes are covered automatically.

## CORS and deployment

The API allows credentials only from `CORS_ORIGINS`, and only the `Content-Type` and
`X-CSRF-Token` request headers. Locally, web (`:3000`) and API (`:8000`) are the same site
(`localhost`), so Lax cookies flow. In production, serve both under the same site (for example
`app.example.com` and `api.example.com`, or a reverse proxy on one origin) and set
`COOKIE_SECURE=true`. Otherwise SameSite=Lax cookies will not be sent.

## Rate limiting

`POST /api/auth/login` and `POST /api/auth/register` share a fixed-window limit per client IP,
stored in Redis: `AUTH_RATE_LIMIT` requests per `AUTH_RATE_WINDOW_SECONDS` (default 10/60 s).
Over the limit, the API returns `429` with `Retry-After`.

- If Redis is unreachable, the limiter **fails open** and logs `rate_limiter_unavailable`, so a
  Redis outage cannot lock the owner out. `/api/health` reports Redis status.
- The client IP comes from the socket. Behind a reverse proxy, configure uvicorn's
  `--proxy-headers`/`--forwarded-allow-ips` so the real client IP is used.

Resume upload and re-parse (the endpoints that can trigger LLM calls) have a separate per-user
limit: `AI_RATE_LIMIT` per `AI_RATE_WINDOW_SECONDS`. Account deletion shares the auth limiter.

## Uploads

- Only PDF, DOCX and TXT are accepted. The type is detected from **content** (`%PDF-`, a ZIP
  containing `word/document.xml`, or valid UTF-8 without NUL bytes), and the extension must
  match. A renamed file is rejected.
- Limits: `MAX_UPLOAD_BYTES` (checked while reading, so oversize uploads aren't fully read), total
  uncompressed DOCX size (protects against zip bombs), `MAX_RESUME_PAGES`, and a maximum extracted
  text length. Encrypted PDFs are rejected.
- Files are stored as `STORAGE_PATH/<user_id>/<random>.<ext>`. The original filename is display
  metadata only, sanitized, and never used as a path. The storage layer refuses keys that
  resolve outside its root.
- Parsing runs in the worker, never in the request, with a hard RQ job timeout
  (`PARSE_JOB_TIMEOUT_SECONDS`). Failures store a short user-facing message, never a stack trace.
- Downloads are served as `attachment` with `X-Content-Type-Options: nosniff` and
  `Cache-Control: private, no-store`.
- Every resume query filters on `user_id`. Another user's resume returns `404`.

## Secrets

- Secrets only come from environment variables (`.env`, which is git-ignored). `.env.example`
  has placeholders only. `make` generates a random `JWT_SECRET` on first run, and the API refuses
  to start with one shorter than 32 characters.
- Secrets are typed as `SecretStr`, so they don't leak into reprs or logs.
- The web container receives only `NEXT_PUBLIC_API_URL`. Backend secrets are never passed to it,
  and only `NEXT_PUBLIC_*` variables reach the browser bundle.
- Logs never include passwords, tokens or cookies. The JSON formatter redacts known-sensitive
  keys as a backstop. Resume text must never be logged (enforced from Phase 2).
- The test suite refuses to run against a database whose name does not end in `_test`.

## Privacy

- Resume text is sent to a third-party LLM **only** when `settings.llm_consent` is on (off by
  default, set on the Settings page with a timestamp) and a provider key is configured.
  Otherwise the local heuristic parser is used.
- `GET /api/me/export` returns everything stored about the user as JSON: account, settings,
  resumes with extracted text, every profile version and LLM usage. It never includes the password hash.
- `DELETE /api/me` requires the password. It deletes the user row, which cascades to every
  user-owned table, deletes the user's stored files and clears the session.
- Resume text is never logged. Log events carry IDs, counts and durations only.
- Personal files (resume PDFs) are git-ignored and must never be committed or used as test
  fixtures. The test resumes are fictional.
