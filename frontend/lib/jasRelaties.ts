// Gegenereerd uit .claude/skills/wetsanalyse/relaties.json; niet handmatig bewerken.
// Draai tools/graph-qa/scripts/genereer_jas_relaties.py (ADR-011).

export type RelatiePaar = { van: string; naar: string; van_subtype?: string; naar_subtype?: string };

export type RelatieType = {
  leesvorm: string;
  invers: string;
  van: readonly string[];
  naar: readonly string[];
  paren: readonly RelatiePaar[];
  drager: "van" | "naar";
  volgorde: boolean;
  tekstueel: boolean;
  methodisch: boolean;
  bron: readonly string[];
};

export const CATALOGUS_VERSIE = "71269e0680bf";

export const RELATIETYPEN: Record<string, RelatieType> = {
  "beeindigt": {
    "leesvorm": "beëindigt",
    "invers": "eindigt door",
    "van": [
      "Rechtsfeit"
    ],
    "naar": [
      "Rechtsbetrekking"
    ],
    "paren": [],
    "drager": "van",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:53",
      "M01",
      "M05"
    ]
  },
  "bevoegde": {
    "leesvorm": "is bevoegd tot",
    "invers": "komt toe aan",
    "van": [
      "Rechtssubject"
    ],
    "naar": [
      "Delegatiebevoegdheid en delegatie-invulling"
    ],
    "paren": [],
    "drager": "naar",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:125",
      "M01"
    ]
  },
  "creeert": {
    "leesvorm": "creëert",
    "invers": "ontstaat door",
    "van": [
      "Rechtsfeit"
    ],
    "naar": [
      "Rechtsbetrekking"
    ],
    "paren": [],
    "drager": "van",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:53",
      "M01",
      "M05"
    ]
  },
  "definieert": {
    "leesvorm": "definieert",
    "invers": "wordt gedefinieerd in",
    "van": [
      "Brondefinitie"
    ],
    "naar": [
      "Rechtssubject",
      "Rechtsobject",
      "Rechtsbetrekking",
      "Rechtsfeit",
      "Variabele en variabelewaarde",
      "Parameter en parameterwaarde",
      "Tijdsaanduiding",
      "Plaatsaanduiding"
    ],
    "paren": [],
    "drager": "van",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:134",
      "M01"
    ]
  },
  "delegatie_over": {
    "leesvorm": "delegeert over",
    "invers": "wordt nader geregeld door",
    "van": [
      "Delegatiebevoegdheid en delegatie-invulling"
    ],
    "naar": [
      "Rechtsbetrekking",
      "Rechtsfeit",
      "Afleidingsregel"
    ],
    "paren": [],
    "drager": "naar",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:125",
      "M01"
    ]
  },
  "invoer": {
    "leesvorm": "is invoer van",
    "invers": "gebruikt als invoer",
    "van": [
      "Variabele en variabelewaarde",
      "Parameter en parameterwaarde",
      "Voorwaarde",
      "Tijdsaanduiding",
      "Rechtssubject",
      "Rechtsobject",
      "Rechtsbetrekking"
    ],
    "naar": [
      "Afleidingsregel"
    ],
    "paren": [],
    "drager": "naar",
    "volgorde": true,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:71",
      "M01",
      "M05",
      "M06"
    ]
  },
  "kenmerk": {
    "leesvorm": "is kenmerk van",
    "invers": "heeft als kenmerk",
    "van": [
      "Variabele en variabelewaarde"
    ],
    "naar": [
      "Rechtssubject",
      "Rechtsobject",
      "Rechtsbetrekking",
      "Rechtsfeit"
    ],
    "paren": [],
    "drager": "naar",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:80",
      "M01"
    ]
  },
  "onderdeel": {
    "leesvorm": "bevat",
    "invers": "is onderdeel van",
    "van": [
      "Rechtsobject"
    ],
    "naar": [
      "Rechtsobject"
    ],
    "paren": [],
    "drager": "van",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": false,
    "bron": [
      "M06",
      "P18"
    ]
  },
  "operand": {
    "leesvorm": "is operand van",
    "invers": "heeft als operand",
    "van": [
      "Variabele en variabelewaarde",
      "Parameter en parameterwaarde",
      "Voorwaarde",
      "Tijdsaanduiding",
      "Rechtssubject",
      "Rechtsobject",
      "Operator"
    ],
    "naar": [
      "Operator"
    ],
    "paren": [],
    "drager": "naar",
    "volgorde": true,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:62",
      "H2:98",
      "M01"
    ]
  },
  "operator_in": {
    "leesvorm": "is operator in",
    "invers": "gebruikt operator",
    "van": [
      "Operator"
    ],
    "naar": [
      "Voorwaarde",
      "Afleidingsregel"
    ],
    "paren": [],
    "drager": "naar",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:62",
      "H2:98",
      "M01"
    ]
  },
  "plaats": {
    "leesvorm": "heeft als plaatsaanduiding",
    "invers": "is plaatsaanduiding van",
    "van": [
      "Rechtsbetrekking",
      "Rechtsfeit",
      "Afleidingsregel",
      "Variabele en variabelewaarde",
      "Parameter en parameterwaarde"
    ],
    "naar": [
      "Plaatsaanduiding"
    ],
    "paren": [],
    "drager": "van",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:116",
      "M01"
    ]
  },
  "plichthebbende": {
    "leesvorm": "is plichthebbende van",
    "invers": "heeft als plichthebbende",
    "van": [
      "Rechtssubject"
    ],
    "naar": [
      "Rechtsbetrekking"
    ],
    "paren": [],
    "drager": "naar",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:44",
      "M01",
      "M02",
      "M05"
    ]
  },
  "rechthebbende": {
    "leesvorm": "is rechthebbende van",
    "invers": "heeft als rechthebbende",
    "van": [
      "Rechtssubject"
    ],
    "naar": [
      "Rechtsbetrekking"
    ],
    "paren": [],
    "drager": "naar",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:44",
      "M01",
      "M02",
      "M05"
    ]
  },
  "tijd": {
    "leesvorm": "heeft als tijdsaanduiding",
    "invers": "is tijdsaanduiding van",
    "van": [
      "Rechtsbetrekking",
      "Rechtsfeit",
      "Afleidingsregel",
      "Variabele en variabelewaarde",
      "Parameter en parameterwaarde"
    ],
    "naar": [
      "Tijdsaanduiding"
    ],
    "paren": [],
    "drager": "van",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:107",
      "M01"
    ]
  },
  "toepassing": {
    "leesvorm": "vindt toepassing op",
    "invers": "past toe",
    "van": [
      "Afleidingsregel"
    ],
    "naar": [
      "Rechtsbetrekking",
      "Rechtsfeit",
      "Afleidingsregel"
    ],
    "paren": [],
    "drager": "van",
    "volgorde": false,
    "tekstueel": true,
    "methodisch": false,
    "bron": [
      "P06",
      "P18"
    ]
  },
  "uitvoer": {
    "leesvorm": "levert op",
    "invers": "is uitvoer van",
    "van": [
      "Afleidingsregel"
    ],
    "naar": [
      "Variabele en variabelewaarde",
      "Rechtssubject",
      "Rechtsobject",
      "Tijdsaanduiding"
    ],
    "paren": [],
    "drager": "van",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:71",
      "M01",
      "M05"
    ]
  },
  "uitzondering_op": {
    "leesvorm": "maakt een uitzondering op",
    "invers": "kent een uitzondering in",
    "van": [
      "Afleidingsregel",
      "Rechtsbetrekking",
      "Voorwaarde"
    ],
    "naar": [
      "Afleidingsregel",
      "Rechtsbetrekking"
    ],
    "paren": [],
    "drager": "van",
    "volgorde": false,
    "tekstueel": true,
    "methodisch": false,
    "bron": [
      "H2:62",
      "P06",
      "P18"
    ]
  },
  "verricht": {
    "leesvorm": "verricht",
    "invers": "wordt verricht door",
    "van": [
      "Rechtssubject"
    ],
    "naar": [
      "Rechtsfeit"
    ],
    "paren": [],
    "drager": "naar",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:53",
      "M01",
      "M05"
    ]
  },
  "voorwaarde": {
    "leesvorm": "geldt onder voorwaarde",
    "invers": "is voorwaarde voor",
    "van": [
      "Rechtsbetrekking",
      "Rechtsfeit",
      "Rechtssubject",
      "Rechtsobject",
      "Afleidingsregel"
    ],
    "naar": [
      "Voorwaarde"
    ],
    "paren": [],
    "drager": "van",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:62",
      "M01",
      "M02",
      "M06"
    ]
  },
  "voorwerp": {
    "leesvorm": "heeft als voorwerp",
    "invers": "is voorwerp van",
    "van": [
      "Rechtsbetrekking",
      "Rechtsfeit"
    ],
    "naar": [
      "Rechtsobject"
    ],
    "paren": [],
    "drager": "van",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:35",
      "M01",
      "M02"
    ]
  },
  "waarde": {
    "leesvorm": "is waarde van",
    "invers": "heeft als waarde",
    "van": [
      "Variabele en variabelewaarde",
      "Parameter en parameterwaarde"
    ],
    "naar": [
      "Variabele en variabelewaarde",
      "Parameter en parameterwaarde",
      "Tijdsaanduiding"
    ],
    "paren": [
      {
        "van": "Variabele en variabelewaarde",
        "van_subtype": "variabelewaarde",
        "naar": "Variabele en variabelewaarde"
      },
      {
        "van": "Parameter en parameterwaarde",
        "van_subtype": "parameterwaarde",
        "naar": "Parameter en parameterwaarde"
      },
      {
        "van": "Parameter en parameterwaarde",
        "van_subtype": "parameterwaarde",
        "naar": "Tijdsaanduiding",
        "naar_subtype": "verbijzondert parameter"
      }
    ],
    "drager": "naar",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:80",
      "H2:89",
      "M01"
    ]
  },
  "wijzigt": {
    "leesvorm": "wijzigt",
    "invers": "wordt gewijzigd door",
    "van": [
      "Rechtsfeit"
    ],
    "naar": [
      "Rechtsbetrekking"
    ],
    "paren": [],
    "drager": "van",
    "volgorde": false,
    "tekstueel": false,
    "methodisch": true,
    "bron": [
      "H2:53",
      "M01",
      "M05"
    ]
  }
};

export const CENTRALE_KLASSEN: readonly string[] = [
  "Rechtsbetrekking",
  "Rechtsfeit",
  "Afleidingsregel",
  "Voorwaarde"
];

export const IMPLICIET_TOEGESTAAN: readonly string[] = [
  "Rechtssubject"
];
