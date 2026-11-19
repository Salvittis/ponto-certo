#!/usr/bin/env bash
set -euo pipefail
umask 077

infra_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
state_dir="${PC_TERRAFORM_STATE_DIR:-$HOME/.local/share/ponto-certo/terraform}"
export PC_TF_CHECKOUT="$(dirname "$infra_dir")" PC_TF_STATE_DIR="$state_dir"
python3 - <<'PY'
import os
from pathlib import Path
checkout = Path(os.environ['PC_TF_CHECKOUT']).resolve()
state = Path(os.environ['PC_TF_STATE_DIR']).expanduser()
if not state.is_absolute():
    raise SystemExit('PC_TERRAFORM_STATE_DIR must be absolute.')
state = state.resolve()
if state == checkout or checkout in state.parents:
    raise SystemExit('Terraform state/data must be outside the repository.')
PY
mkdir -p "$state_dir/data" "$state_dir/workspaces"
chmod 700 "$state_dir" "$state_dir/data" "$state_dir/workspaces"
export TF_DATA_DIR="$state_dir/data"
action="${1:-help}"
if [[ "$#" -gt 0 ]]; then shift; fi

if [[ "$action" == "init" ]]; then
  terraform -chdir="$infra_dir" init \
    -backend-config="path=$state_dir/terraform.tfstate" \
    -backend-config="workspace_dir=$state_dir/workspaces" "$@"
else
  terraform -chdir="$infra_dir" "$action" "$@"
fi
