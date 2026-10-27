# QNAP exporter

## Description
This repository provides a metrics exporter for Qnap NAS. It uses Grafana Alloy's SNMP exporter and remote-writes metrics to Grafana Cloud. A Grafana dashboard is included.

## Container image ![qnap-exporter](https://github.com/bsosnowski/qnap-exporter/actions/workflows/build.yml/badge.svg)
qnap-exporter container images are built for architectures:
- linux/amd64
- linux/arm64 

### Running with Grafana Alloy
The image is based on [Grafana Alloy](https://grafana.com/docs/alloy/latest/) and polls the NAS with
[`prometheus.exporter.snmp`](https://grafana.com/docs/alloy/latest/reference/components/prometheus/prometheus.exporter.snmp/),
then remote-writes the metrics to Grafana Cloud. The SNMP module is generated from the QNAP MIBs at build time
(`docker/snmp/generator.yml`), and the pipeline lives in `docker/config.alloy`.

```shell
docker run -d --name qnap-exporter \
  -e QNAP_SNMP_ADDRESS=192.168.1.100 \
  -e QNAP_SNMP_COMMUNITY=snmp-telegraf \
  -e QNAP_HOSTNAME=NAS453D \
  -e GRAFANA_CLOUD_PROMETHEUS_URL=https://prometheus-prod-XX-prod-REGION.grafana.net/api/prom/push \
  -e GRAFANA_CLOUD_PROMETHEUS_USERNAME=<prometheus instance ID> \
  -e GRAFANA_CLOUD_API_KEY=<access policy token with metrics:write> \
  -p 12345:12345 \
  ghcr.io/bsosnowski/docker/qnap-exporter
```

Optional: `SCRAPE_INTERVAL` (default `60s`) and `SCRAPE_TIMEOUT` (default `50s`). The Alloy UI is on port 12345.

## How to configure NAS

* Open Control Panel and locate the SNMP section
* Enable SNMP with options:
    * Port: 161
    * SNMP Version: SNMP V1/V2
    * Community: snmp-telegraf

## Grafana dashboard overview
Import `charts/qnap-exporter/dashboards/qnap-dashboard.json` into Grafana (on Grafana Cloud: Dashboards → New → Import).
Pick your Prometheus data source and, for the Logs row, your Loki data source from the variables at the top of the dashboard.

### Main
![Main](./pics/Main.png)
### System
![Main](./pics/System.png)
### Cooling
![Main](./pics/Cooling.png)
### Disks
![Main](./pics/Disks.png)
### Network
![Main](./pics/Network.png)
### Logs
This section queries Loki for syslog logs. Logs should be sent in a separate process.
![Main](./pics/Logs.png)

## Helm Chart Configuration
Most important Helm configuration properties.

| Property                    | Description                                                         | Example                                            |
| --------------------------- | ------------------------------------------------------------------- | -------------------------------------------------- |
| nas.hostname                | Value of the `instance` label on every metric                      | NAS453D                                            |
| nas.snmp.address            | host[:port] of the NAS SNMP agent (v2c)                             | 192.168.1.100:161                                  |
| nas.snmp.community          | SNMP community name                                                 | snmp-telegraf                                      |
| nas.scrapeInterval          | How often to poll the NAS                                           | 60s                                                |
| nas.scrapeTimeout           | Timeout for a full SNMP walk                                        | 50s                                                |
| grafanaCloud.prometheusUrl  | Grafana Cloud Prometheus remote_write URL                           | https://prometheus-prod-XX.grafana.net/api/prom/push |
| grafanaCloud.username       | Grafana Cloud Prometheus instance ID                                | 123456                                             |
| grafanaCloud.apiKey         | Access policy token with `metrics:write`                            | glc_...                                            |
| grafanaCloud.existingSecret | Existing Secret with `GRAFANA_CLOUD_API_KEY` and `QNAP_SNMP_COMMUNITY` keys, used instead of `apiKey`/`community` | qnap-exporter-credentials |
| dashboard.enabled           | Ship the dashboard as a ConfigMap for the Grafana sidecar           | false                                              |

## Helm install
```shell
helm install qnap-exporter oci://ghcr.io/bsosnowski/charts/qnap-exporter --version 0.1.1 \
  --set nas.snmp.address=192.168.1.100:161 \
  --set grafanaCloud.prometheusUrl=https://prometheus-prod-XX-prod-REGION.grafana.net/api/prom/push \
  --set grafanaCloud.username=<prometheus instance ID> \
  --set grafanaCloud.apiKey=<access policy token>
```
or just pull:
```shell
 helm pull oci://ghcr.io/bsosnowski/charts/qnap-exporter --version 0.1.1
```

## TODO
- [ ] add support for Syslog -> Loki
- [ ] add support for Prometheus rules