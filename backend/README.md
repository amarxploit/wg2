# SKYGRID API
FastAPI backend starter: email/password registration, JWT login, private file metadata, and shared groups with a maximum of three members.

## Render
Root directory: `backend`
Build command: `pip install -r requirements.txt`
Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
Health path: `/health`

Set environment variables `DATABASE_URL` (Neon connection string), `JWT_SECRET` (random secret at least 32 chars), and `CORS_ORIGINS` (Netlify site origin).

## Neon migration
Run `migrations/001_skygrid.sql` in the Neon SQL editor. Existing schema tables are not dropped. Migration adds group invite tokens.

## Endpoints
- GET /health, GET /ready
- POST /auth/register JSON {email, display_name, password}
- POST /auth/token form fields username=email and password
- GET /auth/me with Bearer token
- POST /groups, GET /groups
- POST /groups/{group_id}/invite, POST /groups/join
- GET /groups/{group_id}/members
- GET /files, GET /files?group_id=..., POST /files

IMPORTANT: /files currently stores metadata only. Real media upload/download and signed object-storage URLs are not implemented. Add rate limits, email verification, password reset, and security review before public launch.
