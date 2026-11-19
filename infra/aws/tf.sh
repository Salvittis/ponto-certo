#!/usr/bin/env bash
# AWS-only wrapper. Never use the Azure state namespace or store credentials here.
set -euo pipefail
umask 077

infra_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
state_dir="${PC_AWS_TERRAFORM_STATE_DIR:-$HOME/.local/share/ponto-certo/terraform-aws}"
terraform_bin="${PC_AWS_TERRAFORM_BIN:-terraform}"
export PC_AWS_TF_CHECKOUT="$(cd "$infra_dir/../.." && pwd -P)"
export PC_AWS_TF_STATE_DIR="$state_dir"
python3 - <<'PY'
import os
from pathlib import Path
checkout = Path(os.environ['PC_AWS_TF_CHECKOUT']).resolve()
state = Path(os.environ['PC_AWS_TF_STATE_DIR'])
if not state.is_absolute():
    raise SystemExit('PC_AWS_TERRAFORM_STATE_DIR must be absolute.')
state = state.resolve()
if state == checkout or checkout in state.parents:
    raise SystemExit('AWS Terraform state/data/cache must be outside the repository.')
azure_dirs = [Path.home()/'.local/share/ponto-certo/terraform']
if os.environ.get('PC_TERRAFORM_STATE_DIR'):
    azure_dirs.append(Path(os.environ['PC_TERRAFORM_STATE_DIR']).expanduser())
for azure in azure_dirs:
    azure = azure.resolve()
    if state == azure or state in azure.parents or azure in state.parents:
        raise SystemExit('AWS and Azure state directories must be separate, not nested.')
PY
mkdir -p "$state_dir/data" "$state_dir/workspaces" "$state_dir/provider-cache"
chmod 700 "$state_dir" "$state_dir/data" "$state_dir/workspaces" "$state_dir/provider-cache"
export TF_DATA_DIR="$state_dir/data"
export TF_PLUGIN_CACHE_DIR="$state_dir/provider-cache"
action="${1:-help}"
if [[ "$#" -gt 0 ]]; then shift; fi

for argument in "$@"; do
  if [[ "$argument" == -backend-config || "$argument" == -backend-config=* ]]; then
    printf 'Backend paths are controlled by the AWS wrapper.\n' >&2
    exit 1
  fi
done

if [[ "$action" == init ]]; then
  "$terraform_bin" -chdir="$infra_dir" init \
    -backend-config="path=$state_dir/terraform.tfstate" \
    -backend-config="workspace_dir=$state_dir/workspaces" "$@"
else
  "$terraform_bin" -chdir="$infra_dir" "$action" "$@"
fi
