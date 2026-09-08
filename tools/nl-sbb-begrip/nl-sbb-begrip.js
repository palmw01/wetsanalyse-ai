export const meta = {
  name: 'nl-sbb-begrip',
  description: 'Genereer NL-SBB conforme definitie en Turtle/RDF voor een wettelijk begrip',
  whenToUse: 'Geef begrip + artikelverwijzingen: { begrip, artikelen, begrippenkader?, uitvoermap? }. Of directe teksten: { begrip, wetteksten, begrippenkader? }',
  phases: [
    { title: 'Regelingen', detail: 'Haal de regelingen met hun afkortingen uit de kennisgraaf' },
    { title: 'Ophalen', detail: 'Haal wetteksten op via de getypeerde graaftools' },
    { title: 'Definitie zoeken', detail: 'Zoek bestaande definitiebepalingen in de kennisgraaf' },
    { title: 'Analyse', detail: 'Analyseer wetteksten en extraheer juridische context' },
    { title: 'Definitie', detail: 'Stel NL-SBB-conforme definitie op (skos:definition + rdfs:comment)' },
    { title: 'Opmaak & Opslaan', detail: 'Genereer Markdown en Turtle en schrijf ze weg' },
  ],
}

// args = { begrip: string, artikelen?: string[], wetteksten?: string[], begrippenkader?: string,
//          uitvoermap?: string }
// artikelen: informele verwijzingen zoals "7a lid 2 Leidraad Inv", "4:89 Awb"
// wetteksten: volledige teksten (backwards compat — slaat het ophalen over)
//
// DEZE WORKFLOW SCHRIJFT GEEN SPARQL. Hij gebruikt de getypeerde graaftools van graph-qa
// (MCP-server `wetsanalyse-graaf`): list_regelingen, get_artikel, get_lid, get_bepaling,
// zoek_definitie. Dat is dezelfde toollaag die Lex gebruikt, en om dezelfde reden: de IRI-opbouw
// zit vol details die je niet aan een prompt moet overlaten. Een artikelnummer met een dubbele punt
// ("4:89" Awb) moet als `artikel:4%3A89` de graaf in; een bepaling van een beleidsregel heeft soms
// geen eigen tekst maar alleen onderdelen; een BWB-nummer dat je zelf invult haalt bij een tikfout
// geen fout op maar de tekst van een ándere wet. Die kennis staat één keer, in geteste code.

const begrip = (args.begrip || '').trim()
if (!begrip) {
  return { fout: 'Geen begrip meegegeven. Roep aan met { begrip: "…", artikelen: [...] }.' }
}
const begrippenkader = args.begrippenkader || 'Algemeen'
const uitvoermap = args.uitvoermap || 'nlsbb-begrippen'

// ── Schemas ───────────────────────────────────────────────────────────────────

const REGELINGEN_SCHEMA = {
  type: 'object',
  required: ['regelingen'],
  properties: {
    regelingen: {
      type: 'array',
      items: {
        type: 'object',
        required: ['bwbr', 'citeertitel'],
        properties: {
          bwbr: { type: 'string', description: 'BWB-id, bijv. BWBR0004770' },
          citeertitel: { type: 'string' },
          soort: { type: 'string', description: 'Zoals de graaf hem geeft: wet, beleidsregel, ministeriele-regeling, …' },
          afkortingen: { type: 'string', description: 'Officiële afkortingen, gescheiden door " | "' }
        }
      }
    }
  }
}

const OPHALEN_SCHEMA = {
  type: 'object',
  required: ['verwijzing', 'gevonden'],
  properties: {
    verwijzing: { type: 'string', description: 'De originele verwijzing zoals meegegeven' },
    gevonden: { type: 'boolean', description: 'false als de verwijzing niet te herleiden of niet op te halen was' },
    bwbr: { type: ['string', 'null'], description: 'BWB-id zoals list_regelingen dat gaf — nooit zelf verzinnen' },
    citeertitel: { type: ['string', 'null'] },
    soort: { type: ['string', 'null'], description: 'Zoals de graaf hem geeft' },
    tekst: { type: ['string', 'null'], description: 'Volledige opgehaalde wettekst met artikel/lid-aanduiding' },
    jci: { type: ['string', 'null'], description: 'JCI-citeerwijze zoals de tool die teruggaf' },
    reden: { type: ['string', 'null'], description: 'Bij gevonden=false: waarom niet' }
  }
}

const DEFINITIE_ZOEK_SCHEMA = {
  type: 'object',
  required: ['bwbr', 'gevonden'],
  properties: {
    bwbr: { type: 'string' },
    gevonden: { type: 'boolean' },
    definitieTekst: { type: ['string', 'null'], description: 'Volledige tekst van de definitiebepaling' },
    artikel: { type: ['string', 'null'], description: 'Artikel en lid waar de definitie staat' },
    jci: { type: ['string', 'null'] }
  }
}

const ANALYSE_SCHEMA = {
  type: 'object',
  required: ['gebruikscontexten', 'grondslagen', 'domein'],
  properties: {
    gebruikscontexten: { type: 'array', items: { type: 'string' } },
    bestaande_definitie_in_wet: { type: ['string', 'null'] },
    grondslagen: {
      type: 'array',
      items: {
        type: 'object',
        required: ['wetnaam', 'artikel'],
        properties: {
          wetnaam: { type: 'string' },
          artikel: { type: 'string' },
          jci: { type: ['string', 'null'], description: 'Overnemen uit de opgehaalde bron; niet verzinnen' },
          url: { type: ['string', 'null'], description: 'Alleen als hij letterlijk in de bron stond' }
        }
      }
    },
    domein: { type: 'string' }
  }
}

const DEFINITIE_SCHEMA = {
  type: 'object',
  required: ['voorkeursterm', 'definitie', 'uitleg'],
  properties: {
    voorkeursterm: { type: 'string' },
    definitie: { type: 'string' },
    uitleg: { type: 'string' }
  }
}

// ── Fase 0: ophalen uit de graaf (alleen als artikelen meegegeven zijn) ────────

var wetteksten = args.wetteksten || []
var bronnen = []

if (args.artikelen && args.artikelen.length > 0) {
  phase('Regelingen')

  // De regelingenlijst kómt uit de graaf; hij wordt niet in dit bestand bijgehouden. Een
  // handgeschreven tabel verouderde hier stil en wees AWR naar het verkeerde BWB-nummer en
  // "Leidraad Inv" naar de Uitvoeringsregeling Awir — en dat levert geen fout op, maar de tekst
  // van een andere wet.
  var regelingenUit = await agent(
    'Roep de tool list_regelingen aan (zonder argumenten) en geef alle regelingen terug die de ' +
    'kennisgraaf bevat: bwbr, citeertitel, soort en de afkortingen zoals ze in het resultaat staan.',
    { label: 'regelingen-ophalen', phase: 'Regelingen', schema: REGELINGEN_SCHEMA }
  )

  var regelingen = (regelingenUit && regelingenUit.regelingen) || []
  if (regelingen.length === 0) {
    return { fout: 'Kon de regelingenlijst niet ophalen. Staat de MCP-server "wetsanalyse-graaf" aan?' }
  }
  log(regelingen.length + ' regelingen in de graaf')

  var REGELINGEN_TABEL = 'REGELINGEN IN DE GRAAF (dit is de enige geldige bron voor een BWB-id):\n' +
    regelingen.map(function (r) {
      return '- ' + r.bwbr + ' · ' + r.citeertitel +
             (r.afkortingen ? ' · afkortingen: ' + r.afkortingen : '') +
             (r.soort ? ' · ' + r.soort : '')
    }).join('\n')

  var TOOL_UITLEG =
    'BESCHIKBARE TOOLS (schrijf zelf GEEN SPARQL — die tools bestaan juist om de valkuilen te dekken):\n' +
    '- get_lid(bwb_id, artikel, lid)      voor een verwijzing MET lid, bijv. "4:89 Awb lid 1"\n' +
    '- get_artikel(bwb_id, artikel)       voor een heel artikel, inclusief zijn leden\n' +
    '- get_bepaling(bwb_id, nummer)       voor een beleidsregel met een decimaal nummer, bijv. "25.1"\n\n' +
    'Geef het artikelnummer door zoals het in de wet staat ("4:89", "36a", "1ca") — de tool zorgt ' +
    'zelf voor de juiste IRI. Kiest de ene tool niets op, probeer dan de andere vorm: een nummer als ' +
    '"7a" is bij de ene regeling een artikel en bij de andere een bepaling.'

  phase('Ophalen')
  log('Ophalen van ' + args.artikelen.length + ' verwijzing(en) uit de kennisgraaf')

  var opgehaald = await pipeline(
    args.artikelen,
    function (verwijzing) {
      return agent(
        'Haal de wettekst op voor de volgende artikelverwijzing uit de kennisgraaf.\n\n' +
        'VERWIJZING: ' + verwijzing + '\n\n' +
        REGELINGEN_TABEL + '\n\n' +
        TOOL_UITLEG + '\n\n' +
        'Stappen:\n' +
        '1. Zoek de regeling op in de lijst hierboven, via haar citeertitel of afkorting. Staat ze ' +
        '   er niet bij, geef dan gevonden=false met een reden — verzin GEEN BWB-nummer.\n' +
        '2. Kies de passende tool en roep hem aan.\n' +
        '3. Formatteer de tekst als: "[Verwijzing] [Citeertitel]: [tekst]"\n' +
        '4. Neem bwbr, citeertitel, soort en de jci over uit wat de tool teruggaf.\n\n' +
        'Geef terug: verwijzing, gevonden, bwbr, citeertitel, soort, tekst, jci, reden',
        { label: 'ophalen-' + verwijzing.replace(/\s+/g, '-').slice(0, 30), phase: 'Ophalen', schema: OPHALEN_SCHEMA }
      )
    }
  )

  var opgehaaldOk = (opgehaald || []).filter(function (r) { return r && r.gevonden && r.tekst })
  if (opgehaaldOk.length === 0) {
    return { fout: 'Ophalen mislukt: geen enkele verwijzing kon worden opgehaald uit de graaf.' }
  }
  var mislukt = (opgehaald || []).filter(function (r) { return !r || !r.gevonden || !r.tekst })
  mislukt.forEach(function (r) {
    log('Niet opgehaald: ' + ((r && r.verwijzing) || '?') + ((r && r.reden) ? ' — ' + r.reden : ''))
  })

  // De vindplaats reist mee. Alleen `tekst` doorgeven zou de jci weggooien die net is opgehaald,
  // waarna de analyse hem zou moeten afleiden — precies de gok die dit platform vermijdt.
  bronnen = opgehaaldOk
  wetteksten = opgehaaldOk.map(function (r) {
    return r.tekst + (r.jci ? '\n[vindplaats: ' + r.jci + ']' : '')
  })

  // Definitiebepalingen zoeken per unieke regeling — óók in beleidsregels en uitvoeringsregelingen.
  // Alleen in wetten zoeken laat bijvoorbeeld artikel 1ca van de Uitvoeringsregeling IW 1990 liggen,
  // dat "betalingsvordering" en "overheidsvordering" gewoon definieert.
  phase('Definitie zoeken')
  var uniekeBwbrs = []
  opgehaaldOk.forEach(function (r) {
    if (r.bwbr && uniekeBwbrs.indexOf(r.bwbr) === -1) uniekeBwbrs.push(r.bwbr)
  })
  log('Zoek definitiebepalingen voor "' + begrip + '" in ' + uniekeBwbrs.length + ' regeling(en): ' + uniekeBwbrs.join(', '))

  var definitieResultaten = await parallel(
    uniekeBwbrs.map(function (bwbr) {
      return function () {
        return agent(
          'Zoek of het begrip "' + begrip + '" wordt gedefinieerd in regeling ' + bwbr + '.\n\n' +
          'Roep de tool zoek_definitie aan met term="' + begrip + '" en bwb_id="' + bwbr + '".\n' +
          'Die tool zoekt op bwb:definieertBegrip en geeft de bepaling terug waar de definitie staat.\n\n' +
          'Geen resultaat: geef gevonden=false terug.\n' +
          'Wel resultaat: geef gevonden=true, de volledige tekst van de definitiebepaling, het ' +
          'artikel/lid en de jci — allemaal letterlijk zoals de tool ze gaf.',
          { label: 'definitie-zoeken-' + bwbr, phase: 'Definitie zoeken', schema: DEFINITIE_ZOEK_SCHEMA }
        )
      }
    })
  )

  var gevondenDefinities = (definitieResultaten || [])
    .filter(function (r) { return r && r.gevonden && r.definitieTekst })
    .map(function (r) {
      return '[WETTELIJKE DEFINITIE uit ' + r.bwbr + (r.artikel ? ', ' + r.artikel : '') + ']\n' +
             r.definitieTekst + (r.jci ? '\n[vindplaats: ' + r.jci + ']' : '')
    })

  if (gevondenDefinities.length > 0) {
    log(gevondenDefinities.length + ' wettelijke definitie(s) gevonden — meegegeven aan analyse')
    wetteksten = gevondenDefinities.concat(wetteksten)
  } else {
    log('Geen definitiebepaling gevonden voor "' + begrip + '" in de opgehaalde regelingen')
  }
}

if (wetteksten.length === 0) {
  return { fout: 'Geen wetteksten beschikbaar. Geef artikelen of wetteksten mee.' }
}

// ── Fase 1: Analyse ───────────────────────────────────────────────────────────

phase('Analyse')
log('Begrip: ' + begrip + ' — analyseer ' + wetteksten.length + ' wettekst(en)')

const analyse = await agent(
  'Analyseer de volgende wetteksten op het begrip "' + begrip + '" en extraheer alle juridische context.\n\n' +
  'WETTEKSTEN:\n' +
  wetteksten.map(function (t, i) { return '--- [' + (i + 1) + '] ---\n' + t }).join('\n\n') + '\n\n' +
  'Geef terug:\n' +
  '- gebruikscontexten: alle zinnen/passages waarin "' + begrip + '" voorkomt\n' +
  '- bestaande_definitie_in_wet: letterlijke wettelijke definitie als aanwezig, anders null\n' +
  '- grondslagen: per passage { wetnaam, artikel, jci, url } — neem jci over uit de "[vindplaats: …]"-regel ' +
  'bij de tekst; laat url leeg tenzij hij letterlijk in de bron staat. Verzin geen vindplaats.\n' +
  '- domein: rechtsdomein (bijv. "Burgerlijk recht")',
  { label: 'analyse-wetteksten', phase: 'Analyse', schema: ANALYSE_SCHEMA }
)

if (!analyse) { return { fout: 'Analyse mislukt of afgebroken.' } }

// ── Fase 2: Definitie ─────────────────────────────────────────────────────────

phase('Definitie')
log('Definitie opstellen conform NL-SBB v1.0.0')

const grondslagen = analyse.grondslagen || []
const grondslagenTekst = grondslagen.map(function (g) {
  return g.artikel + ' ' + g.wetnaam + (g.jci ? ' (' + g.jci + ')' : '')
}).join('; ')

const definitie = await agent(
  'Stel een NL-SBB-conforme definitie op voor het begrip "' + begrip + '".\n\n' +
  'JURIDISCHE ANALYSE:\n' +
  'Gebruikscontexten:\n' + (analyse.gebruikscontexten || []).map(function (c) { return '- ' + c }).join('\n') + '\n\n' +
  'Bestaande wettelijke definitie: ' + (analyse.bestaande_definitie_in_wet || '(geen)') + '\n' +
  'Grondslagen: ' + (grondslagenTekst || '(geen)') + '\n' +
  'Domein: ' + analyse.domein + '\n\n' +
  'REGELS (NL-SBB v1.0.0 — geverifieerd op github.com/Geonovum/NL-SBB):\n' +
  '1. Aanbevolen structuur: "Een [term] is een ... die/dat ..."\n' +
  '2. Definitie moet het begrip onderscheiden van andere begrippen\n' +
  '3. skos:definition is juridisch precies — GEEN B1-vereiste (B1 geldt voor rdfs:comment)\n' +
  '4. Als er een wettelijke definitie is, gebruik die als basis\n' +
  '5. rdfs:comment (uitleg): B1-taal, begrijpelijk zonder vakkennis',
  { label: 'definitie-opstellen', phase: 'Definitie', schema: DEFINITIE_SCHEMA }
)

if (!definitie) { return { fout: 'Definitie opstellen mislukt of afgebroken.' } }

// ── Fase 3: Opmaak & Opslaan ──────────────────────────────────────────────────

phase('Opmaak & Opslaan')
log('Bestanden genereren en wegschrijven')

/** PascalCase-slug zonder leestekens: veilig als IRI-segment én als bestandsnaam. */
function slug(tekst) {
  return String(tekst || '')
    .normalize('NFD').replace(/[̀-ͯ]/g, '')   // diakrieten weg (ë -> e)
    .split(/[^a-zA-Z0-9]+/).filter(Boolean)
    .map(function (w) { return w.charAt(0).toUpperCase() + w.slice(1) })
    .join('')
}

const uriSlug = slug(definitie.voorkeursterm) || slug(begrip) || 'Begrip'
const kaderSlug = slug(begrippenkader) || 'Algemeen'
const bestandsnaam = slug(begrip) || uriSlug

function escapeTtl(s) {
  return s ? String(s)
    .replace(/\\/g, '\\\\').replace(/"/g, '\\"')
    .replace(/\r/g, '\\r').replace(/\n/g, '\\n').replace(/\t/g, '\\t') : ''
}

/** Alleen een http(s)-url zonder witruimte of haken mag als IRI in de Turtle. */
function veiligeUrl(u) {
  return (typeof u === 'string' && /^https?:\/\/[^\s<>"]+$/.test(u)) ? u : null
}

const grondslagMd = grondslagen.length
  ? grondslagen.map(function (g) {
      return '- ' + [g.artikel, g.wetnaam].filter(Boolean).join(', ') +
             (g.jci ? ' — `' + g.jci + '`' : '') + (veiligeUrl(g.url) ? '\n  ' + g.url : '')
    }).join('\n')
  : ''

// Álle grondslagen, niet alleen de eerste: een begrip dat op drie bepalingen rust hoort ze alle
// drie te dragen, anders verdwijnt twee derde van de herkomst zonder melding.
const bronBlok = grondslagen.map(function (g) {
  const url = veiligeUrl(g.url)
  return '\n    dct:source [\n' +
    '        a foaf:Document ;\n' +
    '        dct:title "' + escapeTtl(g.wetnaam) + '"@nl ;\n' +
    '        dct:bibliographicCitation "' + escapeTtl([g.artikel, g.jci].filter(Boolean).join(' — ')) + '"' +
    (url ? ' ;\n        foaf:page <' + url + '>' : '') + '\n' +
    '    ] ;'
}).join('')

const mdInhoud = '# Begrip: ' + definitie.voorkeursterm + '\n\n' +
  '## Definitie\n' + definitie.definitie + '\n\n' +
  '## Uitleg (B1)\n' + definitie.uitleg + '\n\n' +
  '## Grondslag\n' + (grondslagMd || '(geen grondslag geïdentificeerd)') + '\n\n' +
  '## Begrippenkader\n' + begrippenkader + '\n\n' +
  '## URI\nhttp://nlbegrip.nl/id/concept/' + uriSlug + '\n\n' +
  '---\n*Gegenereerd conform NL-SBB v1.0.0 — Standaard voor het Beschrijven van Begrippen*'

const ttlInhoud = '@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n' +
  '@prefix dct:  <http://purl.org/dc/terms/> .\n' +
  '@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n' +
  '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n' +
  '<http://nlbegrip.nl/id/begrippenkader/' + kaderSlug + '> a skos:ConceptScheme ;\n' +
  '    dct:title "' + escapeTtl(begrippenkader) + '"@nl .\n\n' +
  '<http://nlbegrip.nl/id/concept/' + uriSlug + '> a skos:Concept ;\n' +
  '    skos:prefLabel "' + escapeTtl(definitie.voorkeursterm) + '"@nl ;\n' +
  '    skos:definition "' + escapeTtl(definitie.definitie) + '"@nl ;\n' +
  '    rdfs:comment "' + escapeTtl(definitie.uitleg) + '"@nl ;\n' +
  '    skos:inScheme <http://nlbegrip.nl/id/begrippenkader/' + kaderSlug + '> ;' +
  bronBlok + '\n    .'

const mdPad = uitvoermap + '/' + bestandsnaam + '.md'
const ttlPad = uitvoermap + '/' + bestandsnaam + '.ttl'

await agent(
  'Schrijf de volgende twee bestanden weg. Maak de map "' + uitvoermap + '" aan als hij nog niet bestaat.\n' +
  'Neem de inhoud LETTERLIJK over — niet herschrijven, niet herformatteren, niets toevoegen.\n\n' +
  '=== BESTAND 1 ===\nPad: ' + mdPad + '\n\n' + mdInhoud + '\n\n' +
  '=== BESTAND 2 ===\nPad: ' + ttlPad + '\n\n' + ttlInhoud + '\n\n' +
  'Gebruik de Write-tool voor elk bestand. Bevestig dat beide zijn aangemaakt.',
  { label: 'bestanden-schrijven', phase: 'Opmaak & Opslaan' }
)

log('Klaar — ' + mdPad + ' en ' + ttlPad + ' opgeslagen')

return {
  begrip: definitie.voorkeursterm,
  definitie: definitie.definitie,
  uitleg: definitie.uitleg,
  grondslag: grondslagMd,
  bronnen: bronnen.map(function (b) { return { bwbr: b.bwbr, citeertitel: b.citeertitel, jci: b.jci } }),
  uri: 'http://nlbegrip.nl/id/concept/' + uriSlug,
  bestanden: [mdPad, ttlPad]
}
