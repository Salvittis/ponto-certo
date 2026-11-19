#!/usr/bin/env bash
# Reproduces the mandatory security gates without scanner credentials.
set -euo pipefail
cd "$(dirname "$0")/.."
source security/tool-images.env
REPORT_DIR="${SECURITY_REPORT_DIR:-reports/security}"
mkdir -p "$REPORT_DIR"
REPORT_DIR="$(cd "$REPORT_DIR" && pwd)"
PROJECT_DIR="$PWD"

scan_gitleaks() {
  if git rev-parse --git-dir >/dev/null 2>&1; then
    docker run --rm -v "$PROJECT_DIR:/src:ro" -v "$REPORT_DIR:/reports" \
      "$GITLEAKS_IMAGE" git /src --redact=100 --exit-code=1 \
      --report-format=json --report-path=/reports/gitleaks.json
  else
    docker run --rm -v "$PROJECT_DIR:/src:ro" -v "$REPORT_DIR:/reports" \
      "$GITLEAKS_IMAGE" dir /src --redact=100 --exit-code=1 \
      --report-format=json --report-path=/reports/gitleaks.json
  fi
}

scan_semgrep() {
  docker run --rm -e SEMGREP_SEND_METRICS=off -e SEMGREP_ENABLE_VERSION_CHECK=0 \
    -v "$PROJECT_DIR:/src:ro" -v "$REPORT_DIR:/reports" -w /src \
    "$SEMGREP_IMAGE" semgrep scan --config security/semgrep.yml \
    --metrics=off --disable-version-check --strict --error \
    --json-output=/reports/semgrep.json .
}

scan_image() {
  local image_tar="$1"
  if [[ ! -f "$image_tar" ]]; then
    printf 'Image archive not found: %s\n' "$image_tar" >&2
    return 2
  fi
  image_tar="$(cd "$(dirname "$image_tar")" && pwd)/$(basename "$image_tar")"
  local result=0 raw_dir
  raw_dir="$(mktemp -d)"
  docker run --rm -v "$image_tar:/image.tar:ro" -v "$raw_dir:/raw" \
    "$TRIVY_IMAGE" image --input /image.tar --scanners vuln,secret \
    --severity HIGH,CRITICAL --exit-code 1 --timeout 20m \
    --format json --output /raw/trivy.json || result=$?
  # Secret scan output is private until every matched value/code excerpt is removed.
  if [[ -f "$raw_dir/trivy.json" ]]; then
    python3 scripts/sanitize-trivy.py "$raw_dir/trivy.json" "$REPORT_DIR/trivy-image.json"
  fi
  rm -rf "$raw_dir"
  return "$result"
}

case "${1:-all}" in
  gitleaks) scan_gitleaks ;;
  semgrep) scan_semgrep ;;
  image) scan_image "${2:?Usage: scripts/check-security.sh image /absolute/image.tar}" ;;
  all)
    result=0
    scan_gitleaks || result=1
    scan_semgrep || result=1
    if [[ -n "${2:-}" ]]; then scan_image "$2" || result=1; fi
    exit "$result"
    ;;
  *) printf 'Usage: %s {all|gitleaks|semgrep|image} [image.tar]\n' "$0" >&2; exit 2 ;;
esac
