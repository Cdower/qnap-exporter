#!/usr/bin/env python3
"""Checks a running end-to-end stack (see compose.yaml).

The exporter polls a simulated QNAP NAS (snmpsim/data/qnap-e2e.snmprec) and
remote-writes to a Prometheus receiver. This script waits for the data to
arrive, then checks that:

  * every Alloy component is healthy,
  * every Prometheus query in the bundled Grafana dashboard returns data,
  * specific series carry the values and labels the fixture defines, so a
    change in how SNMP values are decoded or labelled is caught,
  * every series carries the configured instance label.

Uses only the standard library so it runs on a bare CI runner.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# (PromQL, expected value). "$host" is replaced with --instance. Values come
# from snmpsim/data/qnap-e2e.snmprec; update both together.
EXPECTED = [
    # NAS-MIB scalars
    ('systemCPU_UsageEX{instance="$host"}', 12),
    ('cpu_TemperatureEX{instance="$host"}', 45),
    ('systemTemperatureEX{instance="$host"}', 38),
    ('systemTotalMemEX{instance="$host"}', 8 * 1024**3),
    # DisplayString overrides: text must arrive as text, not hex.
    ('modelNameEX{instance="$host", modelNameEX="TS-453D"}', 1),
    ('hostNameEX{instance="$host", hostNameEX="NAS453D"}', 1),
    # Tables, with their lookup labels
    ('cpuUsage{instance="$host", cpuIndex="3", cpuID="2"}', 30),
    ('avg(cpuUsage{instance="$host"})', 25),
    ('count(cpuUsage{instance="$host"})', 4),
    ('diskTemperture{instance="$host", diskIndex="4", diskModel="WDC WD40EFRX"}', 34),
    ('diskSummary{instance="$host", diskIndex="1", diskSummary="Good"}', 1),
    ('count(diskTemperture{instance="$host"} * on (instance, diskIndex)'
     ' group_left (diskSummary) diskSummary{instance="$host"})', 4),
    ('sysFanSpeedEX{instance="$host", sysFanDescrEX="System FAN 2"}', 1250),
    ('sysVolumeTotalSizeEX{instance="$host", sysVolumeDescrEX="DataVol1", sysVolumeFSEX="ext4"}',
     10 * 1024**4),
    ('sysVolumeStatusEX{instance="$host", sysVolumeStatusEX="Ready"}', 1),
    ('enclosureSystemTemp{instance="$host", enclosureID="0", enclosureName="NAS453D"}', 41),
    ('ifPacketsReceivedEX{instance="$host", ifDescrEX="eth0"}', 1000000),
    ('iops{instance="$host", blvID="1"}', 150),
    ('latency{instance="$host", blvID="1"}', 7),
    # QTS-MIB
    ('systemTotalMem{instance="$host"} - systemAvailableMem{instance="$host"}', 3 * 1024**3),
    ('sysUptime{instance="$host"}', 123456789),
    ('sshIsEnabled{instance="$host"}', 1),
    ('telnetIsEnabled{instance="$host"}', 0),
    # Alloy's embedded if_mib module
    ('ifMtu{instance="$host", ifName="eth1"}', 9000),
    ('ifPhysAddress{instance="$host", ifName="eth1", ifPhysAddress="24:5E:BE:00:00:02"}', 1),
    # The scrape itself
    ('up{instance="$host"}', 1),
    # Nothing may arrive without the instance relabel applied.
    ('count({__name__=~".+", instance!="$host"}) or vector(0)', 0),
]


def http_get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode()


def query(prom_url, promql):
    url = f"{prom_url}/api/v1/query?" + urllib.parse.urlencode({"query": promql})
    body = json.loads(http_get(url))
    if body.get("status") != "success":
        raise RuntimeError(f"query failed: {promql}: {body.get('error')}")
    return body["data"]["result"]


def wait_for(description, predicate, timeout):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            if predicate():
                print(f"ok   {description}")
                return
        except (urllib.error.URLError, OSError, RuntimeError, ValueError) as err:
            last_error = err
        time.sleep(2)
    detail = f" (last error: {last_error})" if last_error else ""
    raise SystemExit(f"FAIL timed out after {timeout}s waiting for {description}{detail}")


def dashboard_queries(path):
    """Returns the Prometheus expressions of every panel target."""
    with open(path) as f:
        dashboard = json.load(f)

    def panels(items):
        for panel in items:
            yield panel
            yield from panels(panel.get("panels", []))

    exprs = []
    for panel in panels(dashboard.get("panels", [])):
        for target in panel.get("targets", []):
            ds = target.get("datasource") or panel.get("datasource") or {}
            if isinstance(ds, dict) and ds.get("type") == "prometheus" and target.get("expr"):
                exprs.append(target["expr"])
    # Keep order stable but drop duplicates.
    return list(dict.fromkeys(exprs))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--alloy-url", default="http://127.0.0.1:12345")
    parser.add_argument("--prom-url", default="http://127.0.0.1:9090")
    parser.add_argument("--instance", default="e2e-nas")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--dashboard", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "../../charts/qnap-exporter/dashboards/qnap-dashboard.json"))
    args = parser.parse_args()

    host = args.instance
    sub = lambda promql: promql.replace("$host", host)  # noqa: E731

    wait_for("Alloy /-/ready", lambda: "ready" in http_get(f"{args.alloy_url}/-/ready").lower(),
             args.timeout)
    wait_for("receiver /-/ready", lambda: http_get(f"{args.prom_url}/-/ready") is not None,
             args.timeout)
    wait_for(f'a successful scrape of {host} (up == 1)',
             lambda: any(r["value"][1] == "1" for r in query(args.prom_url, sub('up{instance="$host"}'))),
             args.timeout)
    # rate() in the dashboard needs at least two samples.
    wait_for("three remote-written scrapes",
             lambda: any(float(r["value"][1]) >= 3 for r in
                         query(args.prom_url, sub('count_over_time(up{instance="$host"}[5m])'))),
             args.timeout)

    failures = []
    rows = []

    def record(name, ok, detail=""):
        print(f"{'ok  ' if ok else 'FAIL'} {name}{': ' + detail if detail else ''}")
        rows.append((name, ok, detail))
        if not ok:
            failures.append(name)

    # Alloy component health
    components = json.loads(http_get(f"{args.alloy_url}/api/v0/web/components"))
    for comp in components:
        state = comp.get("health", {}).get("state")
        record(f"component {comp.get('localID')} is healthy", state == "healthy",
               "" if state == "healthy" else f"{state}: {comp.get('health', {}).get('message')}")

    # Every dashboard panel query returns data
    exprs = dashboard_queries(args.dashboard)
    if not exprs:
        record("dashboard has Prometheus queries", False, f"none found in {args.dashboard}")
    for expr in exprs:
        try:
            n = len(query(args.prom_url, sub(expr)))
            record(f"dashboard query `{expr}`", n > 0, f"{n} series" if n else "no data")
        except RuntimeError as err:
            record(f"dashboard query `{expr}`", False, str(err))

    # Exact values and labels from the fixture
    for promql, want in EXPECTED:
        try:
            result = query(args.prom_url, sub(promql))
        except RuntimeError as err:
            record(f"`{promql}` == {want}", False, str(err))
            continue
        got = [float(r["value"][1]) for r in result]
        record(f"`{promql}` == {want}", got == [float(want)],
               "" if got == [float(want)] else f"got {got or 'no series'}")

    names = query(args.prom_url, sub('count by (__name__) ({instance="$host"})'))
    print(f"\n{len(names)} metric names received from {host}; "
          f"{len(rows) - len(failures)}/{len(rows)} checks passed")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            icon = ":x:" if failures else ":white_check_mark:"
            f.write(f"### End-to-end exporter test {icon}\n\n")
            f.write(f"{len(rows) - len(failures)}/{len(rows)} checks passed, "
                    f"{len(names)} metric names received.\n\n")
            f.write("| Check | Result |\n|---|---|\n")
            for name, ok, detail in rows:
                cell = (":white_check_mark: " if ok else ":x: ") + detail
                f.write(f"| {re.sub(r'[|]', '&#124;', name)} | {cell} |\n")
            f.write("\n")

    if failures:
        sys.exit(f"\n{len(failures)} check(s) failed")


if __name__ == "__main__":
    main()
