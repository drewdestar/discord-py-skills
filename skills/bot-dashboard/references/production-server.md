## The production server: FastAPI + Pydantic + Depends

When the stdlib demo outgrows localhost, the upgrade is FastAPI +
uvicorn — same endpoints, same database, same auth, no second
framework to learn. Declare a Pydantic response model for every
stats endpoint (`StatsResponse`, `EventItem`, …) so the dashboard
contract is typed and self-documenting, and the OpenAPI schema
can never drift from the code. Wire the two cross-cutting
concerns through `Depends()`, never by repeating code in each
route: `Depends(get_db)` supplies one read-only SQLite session
per request (yield dependency, closed when the request ends), and
`Depends(get_current_discord_user)` supplies the logged-in user
after the auth middleware has checked them. Open `/docs` while
you build: the free Swagger UI is the API debugger — if an
endpoint is wrong there, it is wrong everywhere, and you find out
before the page does. Serve with `uvicorn app:app` and keep the
stdlib demo as the zero-dependency way to check the shape.

Rate limiting and `/metrics`: put a limiter module in front of
the stats endpoint — it is what the checklist line "API responses
are rate-limited" actually means — and add a `GET /metrics`
endpoint exposing counters the dashboard itself can graph:
economy transactions applied, backup age, WAL size, failed
transactions. A dashboard that cannot show its own health is
half a dashboard (see "Health, per source" above).
