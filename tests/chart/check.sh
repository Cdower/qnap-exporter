#!/usr/bin/env bash
# Static checks for the Helm chart. Needs helm and yq v4 (mikefarah).
#
#   tests/chart/check.sh
set -euo pipefail

repo=$(cd "$(dirname "$0")/../.." && pwd)
chart="$repo/charts/qnap-exporter"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

required=(
  --set nas.snmp.address=192.0.2.10:161
  --set grafanaCloud.prometheusUrl=https://prometheus.example.com/api/prom/push
  --set grafanaCloud.username=123456
  --set grafanaCloud.apiKey=dummy
)

failures=0
ok() { echo "ok   $*"; }
fail() { echo "::error::$*"; echo "FAIL $*"; failures=$((failures + 1)); }

echo "--- helm lint"
if helm lint --strict "$chart" "${required[@]}"; then ok "helm lint"; else fail "helm lint"; fi

render() { helm template qnap-exporter "$chart" --namespace qnap-monitoring "$@"; }

render "${required[@]}" >"$tmp/default.yaml"
ok "renders with the required values"

# Missing required values must be rejected, not rendered into a broken pod.
for value in nas.snmp.address grafanaCloud.prometheusUrl grafanaCloud.username grafanaCloud.apiKey; do
  args=()
  for ((i = 1; i < ${#required[@]}; i += 2)); do
    [[ "${required[$i]}" == "$value="* ]] || args+=(--set "${required[$i]}")
  done
  if render "${args[@]}" >/dev/null 2>"$tmp/err"; then
    fail "renders without $value"
  elif grep -q "$value" "$tmp/err"; then
    ok "rejects a missing $value"
  else
    fail "missing $value fails with an unrelated error: $(cat "$tmp/err")"
  fi
done

# The chart overrides the image CMD, and the e2e test runs the same command.
# Keep all three in step so the e2e test exercises what the chart deploys.
port=$(yq '.service.port' "$chart/values.yaml")
chart_args=$(yq -o json -I0 'select(.kind == "Deployment") | .spec.template.spec.containers[0].args' "$tmp/default.yaml")
image_cmd=$(grep '^CMD ' "$repo/docker/Dockerfile" | sed 's/^CMD //' | yq -p json -o json -I0 '.')
compose_cmd=$(yq -o json -I0 '.services.exporter.command' "$repo/tests/e2e/compose.yaml")
image_cmd_for_chart=${image_cmd//0.0.0.0:12345/0.0.0.0:$port}
if [[ "$chart_args" == "$image_cmd_for_chart" ]]; then
  ok "chart container args match the Dockerfile CMD"
else
  fail "chart container args $chart_args differ from the Dockerfile CMD $image_cmd"
fi
if [[ "$compose_cmd" == "$image_cmd" ]]; then
  ok "e2e compose command matches the Dockerfile CMD"
else
  fail "tests/e2e/compose.yaml command $compose_cmd differs from the Dockerfile CMD $image_cmd"
fi

# Every env var config.alloy reads must be settable through chart values.
deployment_env=$(yq '[select(.kind == "Deployment") | .spec.template.spec.containers[0].env[].name] | .[]' "$tmp/default.yaml")
for var in $(grep -o 'sys.env("[A-Z_]*")' "$repo/docker/config.alloy" | sed 's/sys.env("\(.*\)")/\1/' | sort -u); do
  if grep -qx "$var" <<<"$deployment_env"; then
    ok "chart sets $var"
  else
    fail "config.alloy reads $var but the chart does not set it"
  fi
done

# existingSecret: no Secret is rendered and the pod points at the named one.
render "${required[@]}" --set grafanaCloud.existingSecret=my-secret >"$tmp/existing.yaml"
if [[ -z "$(yq 'select(.kind == "Secret") | .metadata.name' "$tmp/existing.yaml")" ]] &&
  [[ "$(yq 'select(.kind == "Deployment") | [.spec.template.spec.containers[0].env[].valueFrom.secretKeyRef.name | select(.)] | unique | .[]' "$tmp/existing.yaml")" == "my-secret" ]]; then
  ok "existingSecret replaces the generated Secret"
else
  fail "existingSecret is not honoured"
fi

# dashboard.enabled ships the dashboard JSON intact.
render "${required[@]}" --set dashboard.enabled=true >"$tmp/dashboard.yaml"
if yq 'select(.kind == "ConfigMap") | .data["qnap-dashboard.json"]' "$tmp/dashboard.yaml" | yq -p json -e '.panels | length > 0' >/dev/null; then
  ok "dashboard ConfigMap carries valid dashboard JSON"
else
  fail "dashboard ConfigMap is missing or not valid JSON"
fi

render "${required[@]}" --set ingress.enabled=true >/dev/null && ok "renders with ingress enabled"

if ((failures > 0)); then
  echo "$failures check(s) failed"
  exit 1
fi
