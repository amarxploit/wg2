# SKYGRID

Minimal photo/video cloud dashboard starter.

## Structure
- `frontend/`: static frontend prototype (Netlify-ready)
- `backend/`: FastAPI health endpoint starter (Render-ready)

## Notes
- This is the UI/API starter, not yet connected to authentication or object storage.
- Configure secrets as environment variables; never commit credentials.
- Large media uploads should go directly to object storage using signed URLs, not through Netlify Functions.
