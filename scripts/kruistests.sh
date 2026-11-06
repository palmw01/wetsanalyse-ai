#!/usr/bin/env bash
#
# De tests die over de grens van een onderdeel lezen, los van de suites.
#
# Een suite draait alleen als zijn eigen pad wijzigt. Een test die de bicep, de frontend of de api leest,
# draait dan niet als alleen die andere kant verandert: de drift gaat stil de poort door en wordt pas rood
# bij een onschuldige PR. Daarom draait dit script bij elke wijziging aan code, in `poort` en in de hook.
#
# De tests worden hier gevonden op wat ze lezen, niet uit een lijst: een nieuwe kruistest kan zo niet vergeten
# worden. Hele bestanden, want de suites zijn traag en deze bestanden niet. Geen database nodig.
#
#   ZONDER_FRONTEND=1  slaat het frontenddeel over (de hook doet dat zonder node_modules).
set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

LEEST='(parents\[[0-9]\]|WORTEL|PROJECT_ROOT|ROOT)[^#]*/ *"(frontend|api|deploy|tools|docs|packages)"'
mislukt=""

draai() {  # $1 = label, $2 = map, rest = commando
  local label="$1" map="$2"; shift 2
  echo "─── kruistests · $label ───"
  ( cd "$map" && "$@" ) || mislukt="$mislukt $label"
}

gevonden() {  # $1 = testmap: de pytest-bestanden die buiten hun onderdeel lezen
  ( cd "$1" && grep -lE "$LEEST" tests/test_*.py )
}

draai "contract" . uv run --no-project --with pytest pytest -q tests/poort --rootdir tests/poort -p no:cacheprovider

# shellcheck disable=SC2046
draai "graph-qa" tools/graph-qa uv run --frozen --extra dev --extra mcp pytest -q $(gevonden tools/graph-qa)
# shellcheck disable=SC2046
draai "api" api uv run --frozen --extra dev pytest -q $(gevonden api)
# shellcheck disable=SC2046
draai "bwb-import" tools/bwb-import uv run --no-project --with-requirements requirements.txt \
  python -m pytest -q $(gevonden tools/bwb-import)

if [ -n "${ZONDER_FRONTEND:-}" ]; then
  echo "─── kruistests · frontend overgeslagen ───"
else
  # shellcheck disable=SC2046
  draai "frontend" frontend npx vitest run \
    $(cd frontend && grep -rlE '\.\./\.\./(tools|api)/' --include='*.test.ts' lib app components)
fi

if [ -n "$mislukt" ]; then
  echo "kruistests mislukt:$mislukt"
  exit 1
fi
echo "kruistests groen."
