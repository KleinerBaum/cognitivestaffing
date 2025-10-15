# Ingestion Notes / Hinweise zur Datenaufnahme

## Redirect handling / Weiterleitungs-Handling

**EN:** The `_fetch_url` helper in `ingest/extractors.py` follows up to **15** consecutive redirects before aborting. This mirrors the safeguards inside `requests` while providing an explicit cap for deployments that expose redirects via `raise_for_status`. Once the limit is exceeded the fetch stops and raises a `ValueError`, making redirect loops visible during monitoring.

**DE:** Der Helper `_fetch_url` in `ingest/extractors.py` folgt maximal **15** Weiterleitungen, bevor der Vorgang abgebrochen wird. Damit spiegeln wir die Schutzmechanismen von `requests` und setzen zugleich ein explizites Limit für Umgebungen, die Weiterleitungen über `raise_for_status` melden. Wird die Grenze überschritten, stoppt der Abruf und wirft einen `ValueError`, sodass Redirect-Schleifen in der Überwachung auffallen.
