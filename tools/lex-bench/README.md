# Lex Bench, het dashboard

Een statische pagina (plan-lex-bench §6): de scorekaart en het verloop per versie van Lex, de verschillen per categorie
en de risicomatrix. Geen backend en geen koppeling met de app of de api.

- **Openen**: `index.html` in een browser, ook als lokaal bestand. De gegevens staan in `data.js` en komen binnen via een
  gewone `<script>`, want `file://` mag geen JSON ophalen.
- **Bijwerken**: `cd tools/graph-qa && uv run python -m eval.lex_bench --dashboard`. Dat leest de meetmappen
  `docs/architectuur/metingen/lex-bench-*` en de risicomatrix (`scripts/risicomatrix.py`), en verandert die nooit. Een
  nieuwe run (`--l1 <naam>`) komt pas op de pagina na deze stap; de poort meldt het als `data.js` achterloopt.
- **Wat hij laat zien**: blind en ontwikkeling altijd apart, elke maat met teller en noemer, en een tabel bij elke
  grafiek. Er is geen totaalcijfer en geen groen of rood oordeel. Zolang een verwachting `concept` is, staat er
  *trendmeting* boven. Van blinde casussen bevat `data.js` alleen de scores en de categorieën.
- **De stijl van Lex**: de tokens zijn overgenomen uit `frontend/app/globals.css` en het beeldmerk uit
  `frontend/merk/lex-merk.svg`. `tests/poort/test_lex_bench_dashboard.py` bewaakt dat ze gelijk blijven. Fira komt van
  Google Fonts; zonder netwerk valt de pagina terug op een systeemlettertype. De grafieken zijn inline SVG, zonder
  bibliotheek.
