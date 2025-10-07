# Ingestion Notes

## Redirect handling

When fetching pages we rely on `_fetch_url` in `ingest/extractors.py`. The helper
now honours up to **15** consecutive redirects before aborting. This mirrors the
behaviour of `requests` (which already enforces its own limit) while keeping a
manual safety net in place for environments that surface redirects via
`raise_for_status`. If more than 15 hops are encountered the fetch is stopped
and a `ValueError` is raised so operators can investigate the loop.
