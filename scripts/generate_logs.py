#!/usr/bin/env python3
"""Generate realistic application + web access logs (backdated over the last N hours).

usage: python3 scripts/generate_logs.py [--hours 24] [--count 3000] [--follow]
  --follow  keep appending live entries every second after the backfill
"""
import argparse, random, time, os
from datetime import datetime, timedelta, timezone

OUT = os.path.join(os.path.dirname(__file__), "..", "logs")
SERVICES = ["auth-service", "payment-service", "order-service", "inventory-service", "notification-service"]
HOSTS = ["web-01", "web-02", "web-03", "db-01"]
USERS = [f"u{n}" for n in range(100, 140)]
MSGS = {
    "INFO": ["Request completed successfully", "User logged in", "Order created", "Cache refreshed", "Health check OK", "Email queued"],
    "WARN": ["Slow database query (>1s)", "Retrying upstream call", "Disk usage at 85%", "Deprecated API called", "Rate limit nearly reached"],
    "ERROR": ["Payment gateway timeout", "Database connection refused", "NullPointerException in OrderProcessor",
              "Failed to authenticate user: invalid token", "Out of memory: heap space", "Upstream service unavailable"],
    "DEBUG": ["Entering handler", "Cache miss for key", "Query plan selected"],
}
# error-prone services get more errors
WEIGHTS = {"payment-service": (60, 15, 22, 3), "auth-service": (70, 15, 12, 3), "order-service": (75, 12, 10, 3),
           "inventory-service": (80, 10, 7, 3), "notification-service": (85, 8, 4, 3)}
LEVELS = ["INFO", "WARN", "ERROR", "DEBUG"]
URLS = ["/", "/login", "/api/orders", "/api/payments", "/api/products", "/api/users", "/checkout", "/static/app.js", "/health"]
IPS = ["203.0.113.%d", "198.51.100.%d", "192.0.2.%d", "8.8.8.%d", "52.95.110.%d"]
AGENTS = ["Mozilla/5.0 (Windows NT 10.0)", "Mozilla/5.0 (Macintosh)", "curl/8.4.0", "python-requests/2.31", "Mozilla/5.0 (iPhone)"]

def app_line(ts):
    svc = random.choice(SERVICES)
    lvl = random.choices(LEVELS, WEIGHTS[svc])[0]
    t = ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond//1000:03d}Z"
    return f'{t} {lvl} [{svc}] host={random.choice(HOSTS)} user={random.choice(USERS)} msg="{random.choice(MSGS[lvl])}"'

def access_line(ts):
    status = random.choices([200, 201, 301, 304, 400, 401, 403, 404, 500, 502, 503], [60, 6, 3, 6, 3, 3, 2, 8, 4, 2, 3])[0]
    url = random.choice(URLS)
    rt = int(random.lognormvariate(4.8, 0.7)) + (1500 if status >= 500 else 0)
    ip = random.choice(IPS) % random.randint(1, 254)
    t = ts.strftime("%d/%b/%Y:%H:%M:%S +0000")
    return f'{ip} - - [{t}] "{random.choice(["GET","GET","GET","POST","PUT"])} {url} HTTP/1.1" {status} {random.randint(200, 50000)} "-" "{random.choice(AGENTS)}" {rt}'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--count", type=int, default=3000)
    ap.add_argument("--follow", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    now = datetime.now(timezone.utc)
    stamps = sorted(now - timedelta(seconds=random.uniform(0, a.hours * 3600)) for _ in range(a.count))
    with open(os.path.join(OUT, "app.log"), "a") as app, open(os.path.join(OUT, "access.log"), "a") as acc:
        for ts in stamps:
            if random.random() < 0.6:
                app.write(app_line(ts) + "\n")
            else:
                acc.write(access_line(ts) + "\n")
    print(f"Wrote {a.count} backdated entries to {os.path.abspath(OUT)}")
    if a.follow:
        print("Following... Ctrl+C to stop")
        with open(os.path.join(OUT, "app.log"), "a") as app, open(os.path.join(OUT, "access.log"), "a") as acc:
            while True:
                ts = datetime.now(timezone.utc)
                if random.random() < 0.6:
                    app.write(app_line(ts) + "\n"); app.flush()
                else:
                    acc.write(access_line(ts) + "\n"); acc.flush()
                time.sleep(1)

if __name__ == "__main__":
    main()
