# Centralized Log Management System (ELK Stack)

Logs from several services are collected from files, parsed by **Logstash**, stored in **Elasticsearch** and visualised in **Kibana**.

```
 logs/app.log ─┐                                   ┌─> Kibana dashboards
               ├─> Logstash (grok/date/geoip) ──> Elasticsearch (logs-YYYY.MM.dd)
 logs/access.log┘
```

## Run it
```bash
python3 scripts/generate_logs.py --count 3000 --hours 24     # sample logs (add --follow for live logs)
docker compose up -d                                          # ES + Logstash + Kibana (needs ~3 GB RAM)
python3 kibana/setup_kibana.py                                # imports data view, saved search, 2 dashboards
```
Open http://localhost:5601/app/dashboards  (Elasticsearch: http://localhost:9200).
Stop with `docker compose down` (add `-v` to delete data).

## Files
| Path | Purpose |
|---|---|
| `docker-compose.yml` | Elasticsearch, Logstash, Kibana 8.13.4 |
| `logstash/pipeline/logstash.conf` | input → grok/date/mutate/geoip → Elasticsearch |
| `scripts/generate_logs.py` | generates application + nginx-style access logs |
| `kibana/setup_kibana.py`, `kibana/dashboards.ndjson` | data view, saved search, 14 visualisations, 2 dashboards |
| `Mini_Project_6_Report.docx` | project report |

## Finding errors (Discover / KQL)
- `log_level : "ERROR"` – all errors
- `log_level : "ERROR" and service : "payment-service"` – errors for one service
- `http_status >= 500` – server errors from the access log
- `log_message : "timeout"` – free-text search
- `tags : "_app_grok_failure"` – lines Logstash failed to parse
