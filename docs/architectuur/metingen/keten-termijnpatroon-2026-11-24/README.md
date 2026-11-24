# Meting keten-termijnpatroon (24 nov 2026)

Soort: *meting*. Code: graph-qa op `1c91d2d7` (voor) en de branch `claude/keten-termijnpatroon-0b40de` (na). Het lichte
regime: één run, een gerichte set.

## Aanleiding

Op acceptatie stelde Lex bij IW 1990 art. 9 lid 1 ("Een belastingaanslag is invorderbaar zes weken na de dagtekening van
het aanslagbiljet.") zes markeringen voor (run `367e895d`). De jurist had daarnaast een Afleidingsregel, "zes weken" als
Parameter, "invorderbaar" als Variabele, en Rechtsbetrekking in plaats van Rechtsfeit voor de zin. De vraag: waar valt
dat weg, en wat zegt de skill?

## Oorzaak per gemiste markering

Lokaal gereproduceerd met de echte parser (`spacy:nl_core_news_md`): dezelfde 8 kandidaten als op acceptatie.

| Markering van de jurist | Waar het misging | Wat de skill zegt | Wat er nu gebeurt |
|---|---|---|---|
| Afleidingsregel "invorderbaar zes weken na de dagtekening van het aanslagbiljet" | De kandidaat bestaat (C003, `DATE_ASSIGNMENT`, alleen AR). Het **model** koos *Geen annotatie*. Op dezelfde vorm koos het model wél AR in IW 52 lid 1 (bundel 3, 20 nov) en in Awir 33 lid 4 (nulmeting hieronder): runvariatie, geen ontbrekende kandidaat. | `markeringslijst.md`: welk tijdstip uit een tijdsaanduiding volgt, beslis je in 3b met een regel op die formulering; "daarvoor is geen extra markering nodig". De AR is toegestaan (M-2-1), niet vereist. | Ongewijzigd: de kandidaat blijft, het model beslist. |
| Parameter "zes weken", met de tijdsaanduiding als "verbijzondert parameter" | De kern "zes weken" (C005, `TEMPORAL_KERNEL`, alleen T) viel af; de lange tijdsaanduiding kreeg het subtype *verbijzondert parameter*. | **De beoordeelde versie wijkt hier af van de skill.** `markeringslijst.md`: "Een termijn is één Tijdsaanduiding. Geef hem niet ook een Parameter"; `jas-klassen-referentie.md` §8 en §10: een duur als "zes weken" is één element Tijdsaanduiding met het subtype *verbijzondert parameter*, en "zes" in woorden is geen los getal. | Ongewijzigd: Lex volgt de skill. |
| Variabele "invorderbaar" | **Geen detector** zag het woord: geen kandidaat, dus niets om te kiezen. In lid 2 toevallig wel, via generiek naamwoordgroepbewijs (`OBJECT_NP`, `ENUMERATED_NP`). | `voorbeelden.md` E03: "invorderbaar" is een Variabele (booleaanse eigenschap van de aanslag); voorbeeld 2: ook ontkend dezelfde variabele. `jas-klassen-referentie.md` §6: de uitvoer van een afleidingsregel is een variabele. | **Hersteld**: een eigen kandidaat-Variabele op de toestand, en die toestand als `uitkomst` van de datumregel. |
| Rechtsbetrekking voor de hele zin (Lex: Rechtsfeit) | Modelkeuze tussen RB en RF (beide aangeboden). | `voorbeelden.md` E01: Rechtsfeit, met Rechtsbetrekking als alternatief "ter beoordeling". De keuze van de jurist is het alternatief dat de skill noemt, geen afwijking. | Ongewijzigd. |

De fragmentgrenzen waren niet het probleem: de duur en de tijdsaanduiding lagen als twee kandidaten klaar.

## De wijziging

- **Gevolgdetector versie 6** (`detectoren/syntactisch.py`, `_toestand_met_moment`): waar de datumregel ontstaat (een
  toestand uit `GEVOLGTOESTAND` met een koppelwerkwoord en een moment, niet ontkend, in de hoofdzin), komt er een tweede
  kandidaat op het woord van de toestand, alleen Variabele, bewijs `STATE_PROPERTY` (regel
  `jas.variabele.toestand_als_uitvoer`, zwak: Variabele heeft determinisme *laag*, dus het model beslist). Het bewijs
  van de datumregel noemt de toestand als `uitkomst`.
- **Subtype**: `STATE_PROPERTY` wijst *variabele* aan.
- **Relatievoorstellen versie 6** (proefvlag): de datumregel krijgt `uitvoer` naar de variabele precies op de
  toestand; de invoer blijft het tijdstip. Zonder die variabele geen uitvoer.
- Generiek: de regel noemt geen term uit de IW; het patroon is "toestand als rechtsgevolg + moment", dezelfde
  voorwaarde als de datumregel.

## Meting zonder model (voor en na)

`meting.py` (detectie, fusie en deterministisch besluit, echte parser, geen model). Gegevens: `voor.json`, `na.json`.

| Bepaling | soort | kandidaten voor → na | V op de toestand voor → na |
|---|---|---|---|
| IW 9.1 | patroon | 8 → 9 | 0/1 → 1/1 |
| IW 9.2 | patroon | 19 → 19 | 2/2 → 2/2 (de eerste krijgt nu ook `STATE_PROPERTY`) |
| IW 52.1 | patroon | 12 → 13 | 0/1 → 1/1 |
| IW 63b.5 | patroon | 14 → 15 | 0/1 → 1/1 |
| IW 9.5, IW 9.7 (telling) | controle | 23, 15 → gelijk | — |
| geen moment, ontkend, bijvoeglijk (synthetisch) | controle | 2, 6, 6 → gelijk | — |
| AWR 13.2, Awb 4:13.1 | controle | 7, 9 → gelijk | — |

Op de controles verandert geen enkele kandidaat. Op de ontwikkelsets van de referentieset (`v1`, 16 casussen; `concept`,
15) levert de nieuwe regel precies één kandidaat op: "invorderbaar" in IW01 (art. 9 lid 1).

## Meting met het model: nulmeting

Live op acceptatie, code `1c91d2d7`, één beurt in het gesprek `acc-test-2026-11-24-termijnpatroon`, met
`doel: {bron_iri}`. Bepaling zonder bestaande laag en buiten Termijnen: **Awir art. 33 lid 4** (de tweede zin heeft het
patroon, de eerste en derde niet: controle binnen de bepaling).

| Run | Tokens | Uitkomst |
|---|---|---|
| `c18dc070` | 14.564 (delta `/api/account/verbruik`, gedeeld account) | 12 voorstellen. AR "invorderbaar zes weken na de dagtekening van de beschikking" gekozen; Tijdsaanduiding met *verbijzondert parameter*; "na" als Operator; "de dagtekening van de beschikking" als Tijdsaanduiding en invoer van de AR; de zin als Rechtsbetrekking. **Geen Variabele "invorderbaar"**: er was geen kandidaat. Geen uitvoer bij de AR. |

Samen met de bestaande runs (IW 9.1 `367e895d`: AR afgewezen; IW 52.1 `a92bd344`: AR gekozen) is de nulmeting: de AR
komt in 2 van 3 runs, de Variabele in 0 van 3, een `uitvoer` in 0 van 3.

## Meting met het model: na de uitrol

Nog niet gedaan: acceptatie draait pas na de merge naar `master` de nieuwe code. Hoe:

- één beurt op Awir 33 lid 4 in een gesprek `acc-test-…` (de laag van de nulmeting is van deze test en mag opnieuw);
- verwacht: een voorstel Variabele "invorderbaar" (subtype *variabele*), en met de AR erbij een relatie `uitvoer`
  (proefvlag `relatieVoorstellen`, aan op acceptatie); de eerste en derde zin zonder nieuwe voorstellen;
- leg de uitkomst vast in een eigen map (`keten-termijnpatroon-2026-11-24-na/` of met de datum van de meting).

## Wat deze meting niet zegt

- Of het model de nieuwe kandidaat kiest: dat meet pas de run na de uitrol.
- Juridische juistheid: de referentie is de skill en de door de jurist beoordeelde versie van art. 9 lid 1, geen
  vastgestelde gold.
- Twee gaten die blijven, buiten deze wijziging:
  - de tweede toestand in IW 9.2 ("en een naheffingsaanslag invorderbaar veertien dagen na …") krijgt geen eigen
    datumregel: de parser hangt hem als voorwerp, niet als nevenschikking met een koppelwerkwoord;
  - de dekking telt een AR van de gevolgdetector niet bij `berekening/afleiding` (`aangetroffen` is 0 op IW 9.1, 52.1
    en Awir 33.4, terwijl er een AR-kandidaat was): `dekking.aangetroffen` telt per detector van de dimensie, en de
    gevolgdetector hoort daar niet bij. Om dezelfde reden telt de nieuwe Variabele niet bij `waarde`.
