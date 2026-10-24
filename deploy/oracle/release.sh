#!/usr/bin/env bash
# Executed on an existing Oracle host; never provisions paid resources.
set -euo pipefail
revision=${1:?revision required}
hostname=${2:?hostname required}
[[ $revision =~ ^[a-f0-9]{40}$ ]] || exit 2
[[ $hostname =~ ^[a-zA-Z0-9.-]+$ ]] || exit 2
exec 9>/opt/vigil/deploy.lock
flock -n 9 || { echo 'Another deployment is active'; exit 1; }
release=/opt/vigil/releases/$revision
archive=/opt/vigil/vigil-$revision.tgz
mkdir -p "$release"
chmod 700 "$release"
tar -xzf "$archive" -C "$release"
test -s /opt/vigil/state/agents.env
cp -p /opt/vigil/state/compose.json /opt/vigil/state/compose.before-release.json
python3 "$release/deploy/oracle/prepare.py" --state-dir /opt/vigil/state --hostname "$hostname"
if ! sudo docker compose -f /opt/vigil/state/compose.json --profile agents --parallel 1 build; then
  cp -p /opt/vigil/state/compose.before-release.json /opt/vigil/state/compose.json
  exit 1
fi
sudo docker compose -f /opt/vigil/state/compose.json --profile agents up -d
sudo python3 "$release/deploy/oracle/verify.py" --compose /opt/vigil/state/compose.json --timeout 600 --agents
curl --fail --silent --show-error --max-time 30 "https://$hostname/login" >/dev/null
printf '%s\n' "$revision" > /opt/vigil/state/deployed-revision
rm "$archive"
echo 'Deployment passed bank, ledger and HTTPS checks; live model evaluation is separate.'
