#!/usr/bin/env bash
# De uitrolpoort – zie action.yml ernaast. Leest alles uit de omgeving:
#   WACHT_APPS, WACHT_RG                 verplicht
#   WACHT_KETEN                          frontend-app voor de rooktest (leeg = geen rooktest)
#   WACHT_ZONDER_REVISIE                 fout | overslaan
#   WACHT_POGINGEN, WACHT_INTERVAL       revisiepoort, default 30 × 10 s
#   KETEN_POGINGEN, KETEN_INTERVAL       rooktest, default 12 × 15 s
set -euo pipefail

: "${WACHT_APPS:?geen apps opgegeven}"
: "${WACHT_RG:?geen resource group opgegeven}"
zonder_revisie="${WACHT_ZONDER_REVISIE:-fout}"
case "$zonder_revisie" in fout|overslaan) ;; *) echo "::error::zonder-revisie: '$zonder_revisie'"; exit 1 ;; esac
pogingen="${WACHT_POGINGEN:-30}"
interval="${WACHT_INTERVAL:-10}"

fout=0
for app in $WACHT_APPS; do
  rev=$(az containerapp show -n "$app" -g "$WACHT_RG" \
          --query "properties.latestRevisionName" -o tsv 2>/dev/null || true)
  if [ -z "$rev" ]; then
    if [ "$zonder_revisie" = "overslaan" ]; then
      echo "::warning::$app heeft geen revisie – overgeslagen."
    else
      echo "::error::$app: geen revisie gevonden"; fout=1
    fi
    continue
  fi
  echo "$app → $rev"
  gezond=""
  mislukt=""
  for _ in $(seq 1 "$pogingen"); do
    st=$(az containerapp revision show -n "$app" -g "$WACHT_RG" --revision "$rev" \
           --query "properties.runningState" -o tsv 2>/dev/null || echo Unknown)
    echo "  $st"
    case "$st" in
      # ScaledToZero is gezond: api en graph-qa kunnen op minReplicas 0 staan en hebben dan na een
      # uitrol zonder verkeer terecht geen replica. Of zo'n revisie echt opkomt, toetst de rooktest
      # hieronder: die wekt api en graph-qa via de frontend.
      Running|RunningAtMaxScale|ScaledToZero) gezond="$st"; break ;;
      Failed|Degraded) echo "::error::$app: revisie $rev kwam niet gezond op ($st)"; mislukt=1; break ;;
    esac
    sleep "$interval"
  done
  if [ -n "$mislukt" ]; then
    fout=1
  elif [ -z "$gezond" ]; then
    echo "::error::$app: revisie $rev werd niet gezond binnen $((pogingen * interval)) s"; fout=1
  fi
done
[ "$fout" -eq 0 ] || exit 1
echo "Alle revisies gezond."

[ -n "${WACHT_KETEN:-}" ] || exit 0

# De rooktest: een draaiende revisie zegt nog niet dat de keten werkt. De frontend meldt met `?keten=1`
# of hij de api en graph-qa bereikt, en geeft anders 503. Meerdere pogingen, want de eerste aanroep kan
# een koude start van de api of graph-qa veroorzaken.
fqdn=$(az containerapp show -n "$WACHT_KETEN" -g "$WACHT_RG" \
         --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null || true)
[ -n "$fqdn" ] || { echo "::error::$WACHT_KETEN: geen publieke ingress gevonden voor de rooktest"; exit 1; }
keten_pogingen="${KETEN_POGINGEN:-12}"
keten_interval="${KETEN_INTERVAL:-15}"
antwoord=$(mktemp)
trap 'rm -f "$antwoord"' EXIT
echo "Rooktest: /api/health?keten=1 op $WACHT_KETEN"
for i in $(seq 1 "$keten_pogingen"); do
  code=$(curl -sS -o "$antwoord" -w '%{http_code}' --max-time 30 "https://$fqdn/api/health?keten=1" \
           2>/dev/null || true)
  echo "  poging $i: HTTP ${code:-000} $(head -c 300 "$antwoord" 2>/dev/null || true)"
  if [ "$code" = "200" ] && jq -e '.keten == "ok" and .api == "ok" and .lex == "ok"' "$antwoord" >/dev/null 2>&1; then
    echo "De keten werkt."
    exit 0
  fi
  # Een frontend van vóór de rooktest kent `?keten` niet (N-1, zie deploy/azure/README.md): hij geeft dan
  # altijd 200 en alleen het veld `api`. Toets daarop, zodat een api- of graph-qa-uitrol niet rood wordt
  # omdat de frontend nog op de vorige versie staat.
  if [ "$code" = "200" ] && jq -e '(has("keten") | not) and .api == "ok"' "$antwoord" >/dev/null 2>&1; then
    echo "::warning::de frontend kent ?keten nog niet; alleen frontend → api getoetst."
    exit 0
  fi
  if [ "$i" -lt "$keten_pogingen" ]; then sleep "$keten_interval"; fi
done
echo "::error::rooktest mislukt: de frontend bereikt de api of graph-qa niet (zie de laatste poging hierboven)"
exit 1
