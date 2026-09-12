# Conceptanalyses Wzt

<!-- Gegenereerd uit cases.json door render_jas_referentieset.py. -->

Status: concept; niet vastgesteld en geen volledige gold-annotaties. Gebruik de reviewvragen om ontbrekende onderdelen en betwiste duidingen af te ronden. Bron-ID’s verwijzen naar [het manifest](../bronnen/manifest.json). Het analysedoel is methodetoetsing van de vastgelegde tekst, niet een individueel besluit.

## WZT01 — 2 lid1

Split: ontwikkeling | Bron: L05 | Versie: webweergave geldend vanaf 2025-01-01, geraadpleegd door broncache 2025-02-26

### Ongewijzigde analysetekst

> Indien de normpremie voor een verzekerde in het berekeningsjaar minder bedraagt dan de standaardpremie in dat jaar, heeft de verzekerde aanspraak op een zorgtoeslag ter grootte van dat verschil. Voor een verzekerde met een partner wordt daarbij tweemaal de standaardpremie in aanmerking genomen; in dat geval worden de verzekerde en zijn partner voor de toepassing van deze wet geacht gezamenlijk één aanspraak te hebben.

### Grammatica en normstructuur

Minder dan is strikt; dat verschil verwijst naar standaardpremie minus normpremie. Tweede zin wijzigt de partnerberekening.

### Conceptmarkeringen

| ID | Fragment | Klasse | Motivering |
|---|---|---|---|

| E01 | Indien de normpremie voor een verzekerde in het berekeningsjaar minder bedraagt dan de standaardpremie in dat jaar, heeft de verzekerde aanspraak op een zorgtoeslag ter grootte van dat verschil. Voor een verzekerde met een partner wordt daarbij tweemaal de standaardpremie in aanmerking genomen; in dat geval worden de verzekerde en zijn partner voor de toepassing van deze wet geacht gezamenlijk één aanspraak te hebben. | Rechtsbetrekking | Dragende normformulering; verdere opdeling vóór goldreview. |

| E02 | de verzekerde | Rechtssubject | Rechthebbende. |

| E03 | een zorgtoeslag | Rechtsobject | Voorwerp van de aanspraak. |

| E04 | minder bedraagt dan | Operator | Strikte vergelijking. |

| E05 | Indien de normpremie voor een verzekerde in het berekeningsjaar minder bedraagt dan de standaardpremie in dat jaar | Voorwaarde | Complete voorwaarde voor de enkelvoudige aanspraak. |

| E06 | de normpremie | Variabele en variabelewaarde | Invoer van de vergelijking. |

| E07 | de standaardpremie | Parameter en parameterwaarde | Vastgestelde referentiepremie voor het jaar; definitie/jaar controleren. |

| E08 | in het berekeningsjaar | Tijdsaanduiding | Referentieperiode van vergelijking en aanspraak. |

| E09 | dat verschil | Variabele en variabelewaarde | Afgeleide verschilwaarde met antecedenten uit de eerste zin. |

| E10 | tweemaal | Operator | Vermenigvuldiging in de partnervariant. |

| E11 | Voor een verzekerde met een partner wordt daarbij tweemaal de standaardpremie in aanmerking genomen; in dat geval worden de verzekerde en zijn partner voor de toepassing van deze wet geacht gezamenlijk één aanspraak te hebben. | Afleidingsregel | Partnerberekening met juridische fictie gezamenlijke aanspraak; nader splitsen kan verdedigbaar zijn. |

### Samenhang

N01: aanspraak bij positieve verschilwaarde. N02: partnervariant en gezamenlijke aanspraak.

### Hypothetische toetsgevallen

Normpremie lager dan standaardpremie: positieve verschilwaarde in de enkelvoudige variant. Gelijk: voorwaarde niet vervuld. Partner: andere berekeningsbasis.

### Dekking en review

Controleer definities verzekerde/partner, vermogensuitsluiting en maandbepaling; tariefwaarden niet uit deze tekst afleiden.

Menselijke beoordeling: **niet uitgevoerd**. Brondekking en volledige annotatiedekking zijn nog niet vastgesteld. Geen kwaliteitsscore toekennen.

## WZT02 — 2 lid2

Split: ontwikkeling | Bron: L05 | Versie: webweergave geldend vanaf 2025-01-01, geraadpleegd door broncache 2025-02-26

### Ongewijzigde analysetekst

> De normpremie bedraagt een percentage van het drempelinkomen in het berekeningsjaar, vermeerderd met een percentage van het toetsingsinkomen van de verzekerde in dat jaar voorzover dat toetsingsinkomen het drempelinkomen te boven gaat. Voor een verzekerde met een partner wordt daarbij het gezamenlijke toetsingsinkomen in aanmerking genomen.

### Grammatica en normstructuur

Voorzover beperkt de inkomenscomponent tot het deel boven de drempel. Partnerzin verandert de inkomensgrondslag.

### Conceptmarkeringen

| ID | Fragment | Klasse | Motivering |
|---|---|---|---|

| E01 | De normpremie bedraagt een percentage van het drempelinkomen in het berekeningsjaar, vermeerderd met een percentage van het toetsingsinkomen van de verzekerde in dat jaar voorzover dat toetsingsinkomen het drempelinkomen te boven gaat. Voor een verzekerde met een partner wordt daarbij het gezamenlijke toetsingsinkomen in aanmerking genomen. | Afleidingsregel | Dragende normformulering; verdere opdeling vóór goldreview. |

| E02 | De normpremie | Variabele en variabelewaarde | Uitkomstgrootheid. |

| E03 | vermeerderd met | Operator | Optelling van componenten. |

| E04 | het drempelinkomen | Variabele en variabelewaarde | Wettelijk gedefinieerde grootheid; parameterduiding beoordelen. |

| E05 | De normpremie bedraagt een percentage van het drempelinkomen in het berekeningsjaar, vermeerderd met een percentage van het toetsingsinkomen van de verzekerde in dat jaar voorzover dat toetsingsinkomen het drempelinkomen te boven gaat. | Afleidingsregel | Volledige berekening van de normpremie. |

| E06 | voorzover dat toetsingsinkomen het drempelinkomen te boven gaat | Voorwaarde | Reikwijdte van de tweede component. |

| E07 | het toetsingsinkomen van de verzekerde | Variabele en variabelewaarde | Persoonsgebonden invoerwaarde. |

| E08 | het gezamenlijke toetsingsinkomen | Variabele en variabelewaarde | Grondslag bij partner. |

| E09 | in het berekeningsjaar | Tijdsaanduiding | Tijdreferentie van de berekening. |

### Samenhang

N01: basiscomponent plus component over inkomensoverschrijding. N02: gezamenlijke inkomensbasis bij partner.

### Hypothetische toetsgevallen

Toetsingsinkomen onder/gelijk/boven drempel: overschrijding niet stilzwijgend negatief maken. Zonder percentages geen numerieke uitkomst.

### Dekking en review

Volg art.1/2lid3 en geldende percentages; beoordeel variabele versus parameter van drempelinkomen.

Menselijke beoordeling: **niet uitgevoerd**. Brondekking en volledige annotatiedekking zijn nog niet vastgesteld. Geen kwaliteitsscore toekennen.

## WZT03 — 2 lid4

Split: ontwikkeling | Bron: L05 | Versie: webweergave geldend vanaf 2025-01-01, geraadpleegd door broncache 2025-02-26

### Ongewijzigde analysetekst

> In afwijking van het eerste lid bedraagt de aanspraak op een zorgtoeslag voor een verzekerde met een partner die geen verzekerde is, vijftig procent van het op grond van het eerste lid berekende bedrag.

### Grammatica en normstructuur

Die geen verzekerde is beperkt partner; in afwijking overschrijft de berekening voor dit geval.

### Conceptmarkeringen

| ID | Fragment | Klasse | Motivering |
|---|---|---|---|

| E01 | In afwijking van het eerste lid bedraagt de aanspraak op een zorgtoeslag voor een verzekerde met een partner die geen verzekerde is, vijftig procent van het op grond van het eerste lid berekende bedrag. | Afleidingsregel | Dragende normformulering; verdere opdeling vóór goldreview. |

| E02 | vijftig procent | Parameter en parameterwaarde | Vaste vermenigvuldigingsfactor. |

| E03 | een partner die geen verzekerde is | Voorwaarde | Kwalificerende beperking van de partner; grens/klasse ter review. |

| E04 | een verzekerde | Rechtssubject | Drager van de aangepaste aanspraak. |

| E05 | het op grond van het eerste lid berekende bedrag | Variabele en variabelewaarde | Invoerwaarde uit de verwijzing naar lid1. |

### Samenhang

N01 koppelt uitkomst van lid1 aan factor0,5, alleen bij de beschreven partnerstatus.

### Hypothetische toetsgevallen

Partner niet verzekerd: halve lid1-uitkomst. Partner wel verzekerd: deze uitzondering niet toepassen. Status onbekend: uitkomst onzeker.

### Dekking en review

Verifieer definitiebereik verzekerde; beoordeel of volledige voorwaardelijke formulering ruimer moet worden gemarkeerd.

Menselijke beoordeling: **niet uitgevoerd**. Brondekking en volledige annotatiedekking zijn nog niet vastgesteld. Geen kwaliteitsscore toekennen.

## WZT04 — 2 lid6

Split: ontwikkeling | Bron: L05 | Versie: webweergave geldend vanaf 2025-01-01, geraadpleegd door broncache 2025-02-26

### Ongewijzigde analysetekst

> Bij regeling van Onze Minister kunnen omtrent het bepaalde in het vijfde lid nadere regels worden gesteld.

### Grammatica en normstructuur

Kunnen duidt facultatieve regelgevende delegatie; omtrent verwijst naar maandelijkse bepaling in lid5.

### Conceptmarkeringen

| ID | Fragment | Klasse | Motivering |
|---|---|---|---|

| E01 | Bij regeling van Onze Minister kunnen omtrent het bepaalde in het vijfde lid nadere regels worden gesteld. | Delegatiebevoegdheid en delegatie-invulling | Dragende normformulering; verdere opdeling vóór goldreview. |

| E02 | Onze Minister | Rechtssubject | Bevoegd orgaan volgens brondefinitie. |

### Samenhang

N01: bevoegdheid tot nadere regels over lid5, geen bewijs dat deze bevoegdheid is gebruikt.

### Hypothetische toetsgevallen

Regeling gevonden: toets inhoud en grondslag. Geen regeling gevonden: inhoud van nadere regels onbekend, niet verzinnen.

### Dekking en review

Volg lid5, definitie Onze Minister en feitelijke delegatie-invulling.

Menselijke beoordeling: **niet uitgevoerd**. Brondekking en volledige annotatiedekking zijn nog niet vastgesteld. Geen kwaliteitsscore toekennen.
