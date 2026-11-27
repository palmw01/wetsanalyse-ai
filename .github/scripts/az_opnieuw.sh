#!/usr/bin/env bash
# `az_opnieuw <az-argumenten>`: een az-aanroep die bij een tijdelijke fout tot vier keer opnieuw gaat, met een groeiende
# wachttijd. Tijdelijk is een netwerkfout, een time-out, 429 of een 5xx van Azure: 17 nov 2026 viel de uitrol van
# graph-qa om op "Network is unreachable" naar management.azure.com, terwijl het image al gebouwd was. Elke andere fout
# (een app die niet bestaat, geen rechten, een ongeldig argument) gaat meteen door met de exitcode van az.
#
# Gebruik: `source .github/scripts/az_opnieuw.sh` en dan `az_opnieuw containerapp update ...`. De publish-workflows,
# promote en rollback doen hun login en image-swap zo; `tests/poort/test_uitrolpoort.py` bewaakt dat.
AZ_OPNIEUW_TIJDELIJK='Network is unreachable|ConnectionError|Connection reset|Connection aborted|Max retries exceeded|timed out|Timeout|ServerTimeout|Temporary failure|Name or service not known|TooManyRequests|429|500 |502 |503 |504 |InternalServerError|ServiceUnavailable|GatewayTimeout'

az_opnieuw() {
  local poging uit rc=1
  for poging in 1 2 3 4; do
    uit=$(az "$@" 2>&1) && { [[ -n "$uit" ]] && printf '%s\n' "$uit"; return 0; }
    rc=$?
    if ! grep -qE "$AZ_OPNIEUW_TIJDELIJK" <<<"$uit"; then
      printf '%s\n' "$uit" >&2
      return "$rc"
    fi
    [[ "$poging" -lt 4 ]] || break
    echo "::warning::az $1 $2: tijdelijke fout (poging $poging van 4), opnieuw over $((poging * 15)) s"
    sleep $((poging * 15))
  done
  printf '%s\n' "$uit" >&2
  return "$rc"
}
