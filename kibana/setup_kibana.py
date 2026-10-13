#!/usr/bin/env python3
"""Create the data view, saved search, visualizations and 2 dashboards in Kibana.
Writes kibana/dashboards.ndjson (importable via Stack Management > Saved Objects)
and imports it into Kibana at $KIBANA_URL (default http://localhost:5601)."""
import json, os, sys, time, urllib.request, uuid

KIBANA = os.environ.get("KIBANA_URL", "http://localhost:5601")
DV = "logs-data-view"
HERE = os.path.dirname(os.path.abspath(__file__))
objs = []

def ref_dv():
    return [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": DV}]

def search_source(query=""):
    return json.dumps({"query": {"query": query, "language": "kuery"}, "filter": [],
                       "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"})

def agg(i, type_, schema, params=None, enabled=True):
    return {"id": str(i), "enabled": enabled, "type": type_, "params": params or {}, "schema": schema}

def terms(i, field, schema, size=10, label=None):
    p = {"field": field, "orderBy": "1", "order": "desc", "size": size, "otherBucket": False,
         "otherBucketLabel": "Other", "missingBucket": False, "missingBucketLabel": "Missing"}
    if label: p["customLabel"] = label
    return agg(i, "terms", schema, p)

COUNT = agg(1, "count", "metric")
DATE = agg(2, "date_histogram", "segment", {"field": "@timestamp", "useNormalizedEsInterval": True,
           "interval": "auto", "drop_partials": False, "min_doc_count": 1, "extended_bounds": {}})

def vis(id_, title, type_, aggs, params, query=""):
    state = {"title": title, "type": type_, "aggs": aggs, "params": params}
    objs.append({"id": id_, "type": "visualization", "attributes": {
        "title": title, "visState": json.dumps(state), "uiStateJSON": "{}", "description": "", "version": 1,
        "kibanaSavedObjectMeta": {"searchSourceJSON": search_source(query)}},
        "references": ref_dv()})
    return id_

def pie(id_, title, field, query="", size=10):
    return vis(id_, title, "pie", [COUNT, terms(2, field, "segment", size)],
               {"type": "pie", "addTooltip": True, "addLegend": True, "legendPosition": "right", "isDonut": True,
                "labels": {"show": True, "values": True, "last_level": True, "truncate": 100}}, query)

def table(id_, title, field, label, query="", size=10):
    return vis(id_, title, "table", [COUNT, terms(2, field, "bucket", size, label)],
               {"perPage": 10, "showPartialRows": False, "showMetricsAtAllLevels": False, "showTotal": False,
                "totalFunc": "sum", "percentageCol": ""}, query)

def metric(id_, title, query=""):
    return vis(id_, title, "metric", [COUNT],
               {"addTooltip": True, "addLegend": False, "type": "metric", "metric": {
                   "percentageMode": False, "useRanges": False, "colorSchema": "Green to Red", "metricColorMode": "None",
                   "colorsRange": [{"from": 0, "to": 10000}], "labels": {"show": True}, "invertColors": False,
                   "style": {"bgFill": "#000", "bgColor": False, "labelColor": False, "subText": "", "fontSize": 60}}}, query)

def bars(id_, title, aggs, query="", mode="stacked", kind="histogram", horizontal=False):
    cat_pos = "left" if horizontal else "bottom"; val_pos = "bottom" if horizontal else "left"
    params = {"type": kind, "grid": {"categoryLines": False},
        "categoryAxes": [{"id": "CategoryAxis-1", "type": "category", "position": cat_pos, "show": True, "style": {},
                          "scale": {"type": "linear"}, "labels": {"show": True, "filter": True, "truncate": 100}, "title": {}}],
        "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value", "position": val_pos, "show": True, "style": {},
                       "scale": {"type": "linear", "mode": "normal"}, "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                       "title": {"text": "Count"}}],
        "seriesParams": [{"show": True, "type": "histogram" if kind == "histogram" else "line", "mode": mode,
                          "data": {"label": "Count", "id": "1"}, "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": True,
                          "lineWidth": 2, "showCircles": True, "interpolate": "linear"}],
        "addTooltip": True, "addLegend": True, "legendPosition": "right", "times": [], "addTimeMarker": False,
        "labels": {"show": False}, "thresholdLine": {"show": False, "value": 10, "width": 1, "style": "full", "color": "#E7664C"}}
    return vis(id_, title, kind, aggs, params, query)

# ---- data view + saved search
objs.append({"id": DV, "type": "index-pattern", "attributes": {"title": "logs-*", "timeFieldName": "@timestamp", "name": "Centralized Logs"}, "references": []})
objs.append({"id": "errors-search", "type": "search", "attributes": {
    "title": "Errors Only (log_level:ERROR)", "description": "Log filtering: all ERROR entries from every service",
    "columns": ["log_type", "service", "log_message", "host_name", "http_status"], "sort": [["@timestamp", "desc"]],
    "grid": {}, "hideChart": False, "isTextBasedQuery": False,
    "kibanaSavedObjectMeta": {"searchSourceJSON": search_source("log_level : \"ERROR\"")}},
    "references": ref_dv()})

E = 'log_level : "ERROR"'
# ---- Dashboard 1: Log Overview
v = {}
v["total"]   = metric("v-total", "Total Log Events")
v["errors"]  = metric("v-errors", "Total Errors", E)
v["warns"]   = metric("v-warns", "Total Warnings", 'log_level : "WARN"')
v["levels"]  = pie("v-levels", "Logs by Level", "log_level.keyword")
v["types"]   = pie("v-types", "Logs by Type (application vs access)", "log_type.keyword")
v["timeline"] = bars("v-timeline", "Log Volume Over Time by Level",
                     [COUNT, DATE, terms(3, "log_level.keyword", "group", 5)])
v["services"] = bars("v-services", "Events per Service", [COUNT, terms(2, "service.keyword", "segment", 10)], horizontal=True, kind="histogram")
v["hosts"]   = table("v-hosts", "Top Hosts", "host_name.keyword", "Host", size=10)

# ---- Dashboard 2: Error Analysis
v["err_time"] = bars("v-err-time", "Errors Over Time", [COUNT, DATE], E, kind="line", mode="normal")
v["err_svc"]  = pie("v-err-svc", "Errors by Service", "service.keyword", E)
v["err_msg"]  = table("v-err-msg", "Top Error Messages", "log_message.keyword", "Error message", E, 10)
v["err_host"] = bars("v-err-host", "Errors by Host", [COUNT, terms(2, "host_name.keyword", "segment", 10)], E, horizontal=True)
v["http"]     = pie("v-http", "HTTP 4xx/5xx Status Codes", "http_status", "http_status >= 400")
v["slow"]     = table("v-slow", "Top URLs Returning 5xx", "url.keyword", "URL", "http_status >= 500", 10)

def dashboard(id_, title, desc, layout, extra_refs=()):
    panels, refs = [], []
    for i, (ref, x, y, w, h, kind) in enumerate(layout):
        panels.append({"version": "8.13.4", "type": kind, "gridData": {"x": x, "y": y, "w": w, "h": h, "i": str(i)},
                       "panelIndex": str(i), "embeddableConfig": {}, "panelRefName": f"panel_{i}"})
        refs.append({"name": f"panel_{i}", "type": kind, "id": ref})
    objs.append({"id": id_, "type": "dashboard", "attributes": {
        "title": title, "description": desc, "hits": 0, "version": 1, "timeRestore": True, "timeFrom": "now-24h", "timeTo": "now",
        "refreshInterval": {"pause": False, "value": 10000}, "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
        "panelsJSON": json.dumps(panels),
        "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})}},
        "references": refs})

V = "visualization"
dashboard("dash-overview", "1. Log Overview", "Volume, level distribution and activity per service/host", [
    (v["total"], 0, 0, 16, 8, V), (v["errors"], 16, 0, 16, 8, V), (v["warns"], 32, 0, 16, 8, V),
    (v["timeline"], 0, 8, 48, 14, V),
    (v["levels"], 0, 22, 16, 14, V), (v["types"], 16, 22, 16, 14, V), (v["hosts"], 32, 22, 16, 14, V),
    (v["services"], 0, 36, 48, 14, V)])
dashboard("dash-errors", "2. Error Analysis", "Identify errors using log filtering (log_level:ERROR, HTTP >= 400)", [
    (v["errors"], 0, 0, 12, 8, V), (v["err_time"], 12, 0, 36, 8, V),
    (v["err_svc"], 0, 8, 16, 14, V), (v["err_msg"], 16, 8, 32, 14, V),
    (v["err_host"], 0, 22, 24, 14, V), (v["http"], 24, 22, 24, 14, V),
    (v["slow"], 0, 36, 48, 12, V),
    ("errors-search", 0, 48, 48, 16, "search")])

nd = os.path.join(HERE, "dashboards.ndjson")
with open(nd, "w") as f:
    for o in objs: f.write(json.dumps(o) + "\n")
print(f"Wrote {len(objs)} saved objects -> {nd}")

if "--no-import" in sys.argv: sys.exit(0)

def req(path, data=None, headers=None):
    r = urllib.request.Request(KIBANA + path, data=data, headers={"kbn-xsrf": "true", **(headers or {})})
    return urllib.request.urlopen(r, timeout=30).read()

for _ in range(60):
    try:
        if json.loads(req("/api/status"))["status"]["overall"]["level"] == "available": break
    except Exception: pass
    print("Waiting for Kibana..."); time.sleep(5)

b = uuid.uuid4().hex
body = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"dashboards.ndjson\"\r\n"
        f"Content-Type: application/ndjson\r\n\r\n").encode() + open(nd, "rb").read() + f"\r\n--{b}--\r\n".encode()
res = json.loads(req("/api/saved_objects/_import?overwrite=true", body, {"Content-Type": f"multipart/form-data; boundary={b}"}))
print("Import success:", res.get("success"), "| objects:", res.get("successCount"), "| errors:", res.get("errors", []))
print(f"Open: {KIBANA}/app/dashboards")
