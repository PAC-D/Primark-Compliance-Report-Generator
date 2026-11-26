#!/usr/bin/env bash
# Pull, rebuild and restart on the server, then check the API. Run from your PC.
# TPS_SSH (default ubuntu@65.2.228.79), TPS_SSH_KEY (path to the private key, optional).
set -euo pipefail
ssh ${TPS_SSH_KEY:+-i "$TPS_SSH_KEY"} "${TPS_SSH:-ubuntu@65.2.228.79}" \
  'set -e; cd /srv/primark-projects/Primark-Compliance-Report-Generator && git pull --ff-only && docker compose build && docker compose up -d && curl --retry 10 --retry-connrefused --retry-delay 2 -fsS http://127.0.0.1:8602/api/health && curl --retry 10 --retry-connrefused --retry-delay 2 -fsS -o /dev/null http://127.0.0.1:8601/compliance/supplier-compliance'
echo
