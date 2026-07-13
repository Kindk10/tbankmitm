#!/usr/bin/env bash
# Залить локальные фиксы на VPS.
#   export VPS_HOST=root@85.192.60.79
#   bash deploy_to_vps.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
HOST="${VPS_HOST:-root@85.192.60.79}"
REMOTE="${VPS_REMOTE_DIR:-~/tbankmitm/tbankmitm}"

FILES=(
  history.py
  browser_ops_injector.py
  operation_detail.py
  panel_bridge.py
  transfer.py
  func.py
  tbank_sbp_debit_injector.py
  mitm_addon_chain.py
  tls_passthrough_hosts.py
  controller.py
  config.json
  nonbank_connect_block.py
  vps_hotfix_inject.py
  _action_buttons_row_inner.html
  _action_buttons_disallow_only_inner.html
  _reference_account_molecule.html
)

LOCAL=()
for f in "${FILES[@]}"; do
  LOCAL+=("$ROOT/$f")
done

echo "Deploy -> ${HOST}:${REMOTE}"
scp "${LOCAL[@]}" "${HOST}:${REMOTE}/"
ssh "$HOST" "cd ${REMOTE} && pkill -f mitm_run_dump || true; sleep 1; export BANK_DEBUG=1 TBANKMITM_PANEL_ALLOW_ANY=1; nohup bash start_vps.sh >/tmp/tbankmitm.log 2>&1 & sleep 2; curl -s -o /dev/null -w 'api %{http_code}\n' http://127.0.0.1:8082/api/operations || true"
echo "Done."
