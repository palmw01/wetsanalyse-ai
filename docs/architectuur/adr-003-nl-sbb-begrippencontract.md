# ADR-003 — NL-SBB is het datacontract voor begrippen

Status: **aangenomen** · Datum: 2026-10-14 · Hoort bij: [PLAN spoor D](../PLAN.md#d-activiteit-3-werkgebieden-en-begrippen)

## Context

Spoor D (activiteit 3) legt begrippen vast op basis van geannoteerde passages. Het plan noemde
NL-SBB tot nu toe alleen bij de projectie naar de graaf, als "beoogde mapping". Dan ontstaat er
eerst een eigen begrippenmodel in de api en de werkplek, dat achteraf naar SKOS vertaald moet
worden. Velden die NL-SBB kent maar wij niet (of andersom) worden zo pas bij de export
zichtbaar, als de opslag, de API-contracten en de begripskaart al vastliggen.

Er is nog niets van spoor D gebouwd. Dit is het moment om het te beslissen.

## Besluit

- **NL-SBB, vastgestelde versie van 10 oktober 2024**
  ([specificatie](https://docs.geostandaarden.nl/nl-sbb/def-st-nl-sbb-20241010/)), is het
  datacontract voor `Begrip`, `BegripRevisie`, `Begrippenkader` en `Begripsrelatie`. De versie is
  vastgepind in de configuratie en staat in de exportmetadata. Een nieuwe versie is een bewuste
  overstap, geen stille update.
- Dat geldt **vanaf levering 2**: het API-contract, de opslag en de velden van de begripskaart
  volgen NL-SBB. De projectie naar de graaf (`skos:Concept`, `skos:ConceptScheme`, `prefLabel`,
  `altLabel`, `definition`, `inScheme`, bronverwijzing) is daarvan een afgeleide, geen vertaling.
- **Analyseobjecten blijven intern.** `Betekenisgroep`, kandidaatbepalingen, termkandidaten en
  bewijssignalen zijn werkmiddelen van de analyse en hebben een eigen formaat. Pas een
  vastgelegd begrip is een NL-SBB-begrip.
- **JAS blijft leidend voor annotaties.** De JAS-duiding van een begrip is een eigen predicaat
  naast NL-SBB. Een JAS-label maakt een begrip geen `skos:narrower` van het methodebegrip.
  Juridische relaties (kwalificatie, uitzondering, voorwaarde bij rechtsgevolg) krijgen eigen
  predicaten en worden niet platgeslagen tot `skos:related`.
- **Identiteit:** een begrip heeft een stabiele IRI `urn:wa:begrip:<uuid>`, los van de
  voorkeursterm. Een andere naam is een revisie, een andere betekenis een nieuw begrip met een
  opvolgingsrelatie (PLAN D, *Datamodel*).
- **Herkomst:** elke begripskoppeling verwijst naar een annotatie-element én naar de bewaarde
  bewijsstand (bronnode, anker, bronhash). De herkomst van de definitie (letterlijk, samengesteld,
  geformuleerd) is een verplicht veld.

## Validatie

- Twee lagen SHACL: de gepubliceerde shapes van de vastgepinde NL-SBB-versie, plus eigen shapes
  voor herkomst (koppeling → element + bewijsstand) en review (status, beoordelaar, tijd).
- Het mechanisme bestaat al voor de JAS-projectie (`api/app/shacl.py`, `api/app/shapes/`). De
  begrippen krijgen er een eigen shapesbestand naast.
- Een begrip heet alleen **NL-SBB-conform** als het tegen die shapes gevalideerd is. Een
  conforme kaart is daarmee nog niet juridisch juist: de juridische review blijft een aparte
  beoordeling.
- **Besloten (16 okt 2026):** diagnostisch, zoals bij de JAS-projectie. Accorderen kan; kaart en
  export tonen of een begrip conform is (PLAN, open keuze 5; bouw in fase F3).
- **Gebouwd (fase F3a, 16 okt 2026):** `api/app/begrip_projectie.py`. De shapes van NL-SBB staan
  letterlijk in `api/app/shapes/nl-sbb-1.0.0.ttl` (toepassingsprofiel `skosapnl:` 1.0.0 uit
  `geonovum/NL-SBB`, CC-BY 4.0, hash getoetst), de eigen shapes in `shapes/begrippen-wa.ttl`.
  "Conform" betekent: geen Violation van het NL-SBB-profiel op het begrip of zijn bronnen;
  waarschuwingen en meldingen van de eigen shapes staan erbij maar beslissen dat niet.

## Gevolgen

- PLAN spoor D verwijst bij *Projectie* naar dit besluit en niet meer naar een "beoogde mapping".
- De begripskaart in de werkplek toont de NL-SBB-velden met Nederlandse labels. IRI's en
  technische namen staan alleen in de details.
- `tools/nl-sbb-begrip` (losse agentworkflow, Markdown + SKOS-Turtle per begrip) is prior art
  voor de veldkeuze en de Turtle-vorm, geen onderdeel van de dienst.
- Uitwisseling met andere terminologietools (TBX) is een latere vraag; zie het
  [INT-terminologieonderzoek](../wetsanalyse/onderzoek-int-terminologie-2026-10-08/README.md).
- **SKOS-LEX**, de juridische uitbreiding die NL-SBB bespreekt, is een onderzoekspunt: de mapping
  op JAS is nog niet onderzocht en hoort niet bij dit besluit.

## Alternatieven

- **Eigen begrippenmodel, NL-SBB alleen bij de export.** Afgewezen: dubbel modelwerk, en drift
  tussen opslag en export die pas laat zichtbaar wordt.
- **Alleen SKOS, zonder NL-SBB-profiel.** Afgewezen: SKOS zegt niets over verplichte velden,
  bronverwijzing of de vorm van een definitie. NL-SBB is het Nederlandse overheidsprofiel daarvoor
  en maakt uitwisseling met andere begrippenkaders mogelijk.

## Aanvulling (spoor I, 27 okt 2026)

- **Het slanke model.** Een begrip draagt alleen wat NL-SBB vraagt: term (naam, alternatieve termen),
  definitie (`skos:definition`), uitleg (`rdfs:comment`), toelichting (`skos:scopeNote`, het veld `context`)
  en voorbeelden (`skos:example`). JAS-duiding, begripstype, geldigheid, eigenschappen, onderbouwing en open
  vragen zijn vervallen; de herkomst van de definitie leidt de api af (alleen een overgenomen brondefinitie
  is letterlijk). De bron blijft `dct:source` via de dragende passages.
- **B1.** De uitleg is in eenvoudige taal, op taalniveau B1; Lex toetst haar in code
  (`begrip_b1`: zinslengte, aantal zinnen, lijdende vorm, moeilijke woorden, onverklaarde vaktermen,
  herhaalde definitie) en meldt treffers als aandachtspunten.
- **TOOI.** Het kader krijgt `dct:subject` naar een thema uit tooitop; een brondocument
  `dct:publisher` naar de TOOI-organisatie van zijn regeling.
