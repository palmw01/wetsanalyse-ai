// Gegenereerd door `python -m eval.lex_bench --dashboard`; niet met de hand bewerken.
window.LEX_BENCH = {
 "schema": "lex-bench-dashboard-1",
 "meetas": "bronselectie",
 "manifest": {
  "versie": "bench-bronselectie-v1",
  "hash": "3986e4619bd3b93bd526e75b1707bdccf022d3c8222334f88326a0261bc4c85f",
  "vastgesteld": 0,
  "casussen": 6
 },
 "runs": [
  {
   "map": "lex-bench-2026-11-17-nulpunt",
   "run": {
    "schema": "lex-bench-run-1",
    "naam": "nulpunt",
    "datum": "2026-11-17",
    "arm": "L1",
    "route": "zoekvragen standaard (stap 8)",
    "code": {
     "commit": "39221e2d1131e12aaca21b24254e3c6546aaa814",
     "schoon": true
    },
    "zoekversie": "za28985cb2f88",
    "images": null,
    "model": null,
    "team": null,
    "casusset": {
     "versie": "bench-bronselectie-v1",
     "hash": "3986e4619bd3b93bd526e75b1707bdccf022d3c8222334f88326a0261bc4c85f"
    },
    "graaftoestand": {
     "LB-01": {
      "pad": "docs/wetsanalyse/referentieset-bronselectie/termijnen-deelvragen-concept/graafantwoorden.json",
      "sha256": "52dfd0c936c2ae9bdfe621b5d26343534e17425fd560cc3587835eca91b92194",
      "graaftoestand": "acceptatie, 16 nov 2026"
     },
     "LB-02": {
      "pad": "docs/wetsanalyse/referentieset-bronselectie/kwijtschelding-concept/graafantwoorden.json",
      "sha256": "72d2f984752a597d5ec3ac109510264f631f6469cef360dd880b8f329cc6a5b5",
      "graaftoestand": "acceptatie, 4 nov 2026"
     },
     "LB-03": {
      "pad": "docs/wetsanalyse/referentieset-bronselectie/bestuurdersaansprakelijkheid-concept/graafantwoorden.json",
      "sha256": "779c14e125683af0a3f6aa6d5f0af247ec668866aeb29793b5bfa8075a0e7464",
      "graaftoestand": "acceptatie, 3 nov 2026"
     },
     "LB-04": {
      "pad": "docs/wetsanalyse/referentieset-bronselectie/bezwaar-ontvankelijkheid-concept/graafantwoorden.json",
      "sha256": "35c5fbf7c8785259fae07846c246f083f0949a947f52f94d50f15071abd2eeca",
      "graaftoestand": "acceptatie, 21 okt 2026"
     },
     "LB-05": {
      "pad": "docs/wetsanalyse/referentieset-bronselectie/invorderbaarheid-deelvragen-concept/graafantwoorden.json",
      "sha256": "8c11c0a47d570c4dc6d5140d83211f3a1f0df73254f488c703756f88cfd5cbe0",
      "graaftoestand": "acceptatie, 3 nov 2026"
     },
     "LB-06": {
      "pad": "docs/wetsanalyse/referentieset-bronselectie/rekeningafspraken-deelvragen-concept/graafantwoorden.json",
      "sha256": "946972b0cf83207af141901229deda4b4660c207cfe0ebe1865523a9e07cf3a9",
      "graaftoestand": "acceptatie, 16 nov 2026 (opname nog niet gemaakt)"
     }
    },
    "verwachting": {
     "LB-01": {
      "sha256": "421c5e0eb53a0822d5e8d749e5b4927cf0bad4dac5833dbb4e726957f820c357",
      "status": "concept"
     },
     "LB-02": {
      "sha256": "9f6e98df124d5797b5c8a3b290b37f34f7c9631d67a1b090da7a5a692752f04f",
      "status": "concept"
     },
     "LB-03": {
      "sha256": "8f08810db1fb530ddb446bd8df259e269b9bc226978e5905dfd1f3b872f5733c",
      "status": "concept"
     },
     "LB-04": {
      "sha256": "62281d49b3ebba6bb81e02512f21507dc46c75621e05a61dd9cc5104372b00d9",
      "status": "concept"
     },
     "LB-05": {
      "sha256": "498d52d7982c7d394e4c69b94346b20865b576120d2dca81509b7bf7d4fa48f4",
      "status": "concept"
     },
     "LB-06": {
      "sha256": "ad5b2b05fc0502f8d2a937ff19a81c4b7dd1c87e54a0bf7c0a27a4764c70e762",
      "status": "concept"
     }
    },
    "verbruik": {
     "L1": 0
    },
    "plafonds": null
   },
   "rapport": {
    "schema": "lex-bench-rapport-1",
    "casussen": [
     {
      "casus_id": "LB-01",
      "naam": "Termijnen",
      "niveau": "moeilijk",
      "gebruik": "ontwikkeling",
      "verwachting": "concept",
      "route": "zoekvragen standaard (stap 8)",
      "maten": {
       "recall_nodig": {
        "teller": 1,
        "noemer": 16,
        "waarde": 0.062
       },
       "recall": {
        "teller": 1,
        "noemer": 18,
        "waarde": 0.056
       },
       "recall_exact": {
        "teller": 1,
        "noemer": 18,
        "waarde": 0.056
       },
       "precisie": {
        "teller": 1,
        "noemer": 24,
        "waarde": 0.042
       },
       "overlap": {
        "teller": 1,
        "noemer": 41,
        "waarde": 0.024
       }
      },
      "diagnose": {
       "uitgesloten_in_keuze": 12,
       "opname_onvolledig": 0
      },
      "categorieen": {
       "lex_mist": 17,
       "lex_onterecht": 23,
       "team_mist": 0,
       "twijfel": 0,
       "status": "voorstel van de code; de reviewer en de jurist volgen in LB2"
      },
      "verschillen": {
       "lex_mist": [
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0002320:artikel:13:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0002320:artikel:13:lid:2",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0002320:artikel:14:lid:1",
         "rol": "aanverwant",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:6",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:2:lid:2:o:e",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:24:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:24:lid:2",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie24%2FCirculaire.divisie24.3",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:6",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:5",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:6",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:7",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:24:lid:2",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.1",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.2",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.3",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:16",
         "rol": "aanverwant",
         "plek": "onbekend"
        }
       ],
       "lex_onterecht": [
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie79%2FCirculaire.divisie79.5",
         "uitgesloten": true
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie79%2FCirculaire.divisie79.3",
         "uitgesloten": true
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0024096:artikel:79.5a",
         "uitgesloten": true
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:30:lid:2",
         "uitgesloten": true
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:5",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:7",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie10%2FCirculaire.divisie10.1",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie10%2FCirculaire.divisie10.3",
         "uitgesloten": true
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:30:lid:2",
         "uitgesloten": true
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie79%2FCirculaire.divisie79.5",
         "uitgesloten": true
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:19:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie79%2FCirculaire.divisie79.3",
         "uitgesloten": true
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:artikel:79.5a",
         "uitgesloten": true
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:7",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:10:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:30:lid:2",
         "uitgesloten": true
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie79%2FCirculaire.divisie79.3",
         "uitgesloten": true
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie79%2FCirculaire.divisie79.5",
         "uitgesloten": true
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:28:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:28a:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:15:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:19:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:19:lid:9",
         "uitgesloten": false
        }
       ]
      }
     },
     {
      "casus_id": "LB-02",
      "naam": "Kwijtschelding voor particulieren",
      "niveau": "moeilijk",
      "gebruik": "ontwikkeling",
      "verwachting": "concept",
      "route": "zoekvragen standaard (stap 8)",
      "maten": {
       "recall_nodig": {
        "teller": 7,
        "noemer": 21,
        "waarde": 0.333
       },
       "recall": {
        "teller": 7,
        "noemer": 24,
        "waarde": 0.292
       },
       "recall_exact": {
        "teller": 7,
        "noemer": 24,
        "waarde": 0.292
       },
       "precisie": {
        "teller": 7,
        "noemer": 32,
        "waarde": 0.219
       },
       "overlap": {
        "teller": 7,
        "noemer": 49,
        "waarde": 0.143
       }
      },
      "diagnose": {
       "uitgesloten_in_keuze": 0,
       "opname_onvolledig": 0
      },
      "categorieen": {
       "lex_mist": 17,
       "lex_onterecht": 25,
       "team_mist": 0,
       "twijfel": 0,
       "status": "voorstel van de code; de reviewer en de jurist volgen in LB2"
      },
      "verschillen": {
       "lex_mist": [
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:26:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:7:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:11",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:10",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:13:lid:1",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.2%2FCirculaire.divisie26.2.10",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:12:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:12:lid:3",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.2%2FCirculaire.divisie26.2.1",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:7:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.1%2FCirculaire.divisie26.1.2",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.1%2FCirculaire.divisie26.1.3",
         "rol": "aanverwant",
         "plek": "onbekend"
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:24",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:25:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.4%2FCirculaire.divisie26.4.1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.1%2FCirculaire.divisie26.1.6",
         "rol": "aanverwant",
         "plek": "onbekend"
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.1%2FCirculaire.divisie26.1.7",
         "rol": "aanverwant",
         "plek": "onbekend"
        }
       ],
       "lex_onterecht": [
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:26:lid:5",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:1d:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:25:lid:5",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:25:lid:8",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:25:lid:9",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:1e:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:25:lid:11",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.2%2FCirculaire.divisie26.2.6",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.2%2FCirculaire.divisie26.2.7",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.4%2FCirculaire.divisie26.4.4",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.1%2FCirculaire.divisie26.1.4",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie74%2FCirculaire.divisie74.1%2FCirculaire.divisie74.1.1",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:1f:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:26:lid:5",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:26a:lid:5",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:26a:lid:7",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:4:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:8:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.4%2FCirculaire.divisie26.4.2",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:25a:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:25b:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:8:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:25:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:3:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:25:lid:2",
         "uitgesloten": false
        }
       ]
      }
     },
     {
      "casus_id": "LB-03",
      "naam": "Bestuurdersaansprakelijkheid",
      "niveau": "gemiddeld",
      "gebruik": "ontwikkeling",
      "verwachting": "concept",
      "route": "zoekvragen standaard (stap 8)",
      "maten": {
       "recall_nodig": {
        "teller": 8,
        "noemer": 18,
        "waarde": 0.444
       },
       "recall": {
        "teller": 9,
        "noemer": 22,
        "waarde": 0.409
       },
       "recall_exact": {
        "teller": 7,
        "noemer": 22,
        "waarde": 0.318
       },
       "precisie": {
        "teller": 7,
        "noemer": 32,
        "waarde": 0.219
       },
       "overlap": {
        "teller": 9,
        "noemer": 47,
        "waarde": 0.191
       }
      },
      "diagnose": {
       "uitgesloten_in_keuze": 0,
       "opname_onvolledig": 0
      },
      "categorieen": {
       "lex_mist": 13,
       "lex_onterecht": 25,
       "team_mist": 0,
       "twijfel": 0,
       "status": "voorstel van de code; de reviewer en de jurist volgen in LB2"
      },
      "verschillen": {
       "lex_mist": [
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:36:lid:7",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie36%2FCirculaire.divisie36.4%2FCirculaire.divisie36.4.1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie36%2FCirculaire.divisie36.6%2FCirculaire.divisie36.6.1",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:36:lid:2",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie36%2FCirculaire.divisie36.5%2FCirculaire.divisie36.5.1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie36%2FCirculaire.divisie36.5%2FCirculaire.divisie36.5.4",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie36%2FCirculaire.divisie36.5%2FCirculaire.divisie36.5.2",
         "rol": "aanverwant",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie36%2FCirculaire.divisie36.5%2FCirculaire.divisie36.5.8",
         "rol": "aanverwant",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:36:lid:6",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie36%2FCirculaire.divisie36.6%2FCirculaire.divisie36.6.2",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:49:lid:3",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie49%2FCirculaire.divisie49.3%2FCirculaire.divisie49.3.1",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie49%2FCirculaire.divisie49.8%2FCirculaire.divisie49.8.1",
         "rol": "aanverwant",
         "plek": "onbekend"
        }
       ],
       "lex_onterecht": [
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:36:lid:8",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:36a:lid:4",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:36:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:32:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:32:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:34:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:34:lid:5",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:35:lid:5",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:35:lid:6",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:35a:lid:5",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:36:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:45:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:34:lid:4",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie36%2FCirculaire.divisie36.6%2FCirculaire.divisie36.6.3",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie33%2FCirculaire.divisie33.7",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie35%2FCirculaire.divisie35.8%2FCirculaire.divisie35.8.1",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:36:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie35%2FCirculaire.divisie35.3%2FCirculaire.divisie35.3.2",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie35%2FCirculaire.divisie35.3%2FCirculaire.divisie35.3.3",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:49:lid:6",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:51:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:52:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:57a:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie36%2FCirculaire.divisie36.7",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie36%2FCirculaire.divisie36.5%2FCirculaire.divisie36.5.1",
         "uitgesloten": false
        }
       ]
      }
     },
     {
      "casus_id": "LB-04",
      "naam": "Ontvankelijkheid van bezwaar tegen een belastingaanslag",
      "niveau": "gemiddeld",
      "gebruik": "ontwikkeling",
      "verwachting": "concept",
      "route": "zoekvragen standaard (stap 8)",
      "maten": {
       "recall_nodig": {
        "teller": 6,
        "noemer": 15,
        "waarde": 0.4
       },
       "recall": {
        "teller": 7,
        "noemer": 19,
        "waarde": 0.368
       },
       "recall_exact": {
        "teller": 7,
        "noemer": 19,
        "waarde": 0.368
       },
       "precisie": {
        "teller": 6,
        "noemer": 32,
        "waarde": 0.188
       },
       "overlap": {
        "teller": 7,
        "noemer": 45,
        "waarde": 0.156
       }
      },
      "diagnose": {
       "uitgesloten_in_keuze": 0,
       "opname_onvolledig": 0
      },
      "categorieen": {
       "lex_mist": 12,
       "lex_onterecht": 26,
       "team_mist": 0,
       "twijfel": 0,
       "status": "voorstel van de code; de reviewer en de jurist volgen in LB2"
      },
      "verschillen": {
       "lex_mist": [
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:6%3A7",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:6%3A8:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0002320:artikel:22j",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:6%3A5:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:6%3A6",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:6%3A5:lid:3",
         "rol": "aanverwant",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0002320:artikel:24a:lid:1",
         "rol": "aanverwant",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:6%3A9:lid:2",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:7%3A1:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0002320:artikel:26a:lid:2",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:1%3A2:lid:1",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:8%3A1",
         "rol": "aanverwant",
         "plek": "onbekend"
        }
       ],
       "lex_onterecht": [
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:6%3A8:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:7%3A10:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0002320:artikel:25b:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:7%3A1a:lid:4",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:6%3A11",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0002320:artikel:24a:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:6%3A8:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0002320:artikel:25c:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:7%3A1a:lid:4",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:7%3A1a:lid:5",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:7%3A1a:lid:6",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:7%3A4:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:6%3A10:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:7%3A11:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:7%3A1a:lid:4",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:7%3A1a:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:6%3A15:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:7%3A4:lid:5",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:7%3A4:lid:6",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0002320:artikel:25b:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0002320:artikel:25e:lid:4",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0002320:artikel:66a:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:10%3A3:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0002320:artikel:24a:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0002320:artikel:25:lid:4",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0002320:artikel:26:lid:1",
         "uitgesloten": false
        }
       ]
      }
     },
     {
      "casus_id": "LB-05",
      "naam": "Invorderbaarheid van belastingaanslagen",
      "niveau": "gemiddeld",
      "gebruik": "ontwikkeling",
      "verwachting": "concept",
      "route": "zoekvragen standaard (stap 8)",
      "maten": {
       "recall_nodig": {
        "teller": 5,
        "noemer": 11,
        "waarde": 0.455
       },
       "recall": {
        "teller": 6,
        "noemer": 18,
        "waarde": 0.333
       },
       "recall_exact": {
        "teller": 6,
        "noemer": 18,
        "waarde": 0.333
       },
       "precisie": {
        "teller": 6,
        "noemer": 32,
        "waarde": 0.188
       },
       "overlap": {
        "teller": 6,
        "noemer": 44,
        "waarde": 0.136
       }
      },
      "diagnose": {
       "uitgesloten_in_keuze": 0,
       "opname_onvolledig": 0
      },
      "categorieen": {
       "lex_mist": 12,
       "lex_onterecht": 26,
       "team_mist": 0,
       "twijfel": 0,
       "status": "voorstel van de code; de reviewer en de jurist volgen in LB2"
      },
      "verschillen": {
       "lex_mist": [
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:10",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:8:lid:1",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.4",
         "rol": "aanverwant",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.5",
         "rol": "aanverwant",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:10:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:10:lid:2",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:8",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie10%2FCirculaire.divisie10.1",
         "rol": "aanverwant",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:6",
         "rol": "aanverwant",
         "plek": "onbekend"
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.1",
         "rol": "aanverwant",
         "plek": "onbekend"
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:25:lid:1",
         "rol": "afhankelijkheid",
         "plek": "onbekend"
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie25%2FCirculaire.divisie25.2",
         "rol": "aanverwant",
         "plek": "onbekend"
        }
       ],
       "lex_onterecht": [
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:5",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:6",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:7",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:8:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:10:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie76%2FCirculaire.divisie76.4",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:62bis:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:15:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:11",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:63ab:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:62bis:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0024096:artikel:79.9a",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:13:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:10:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:28:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie10%2FCirculaire.divisie10.7",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:15:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:19:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:62bis:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie79%2FCirculaire.divisie79.4a",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie28%2FCirculaire.divisie28.3",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0024096:artikel:79.9a",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie30%2FCirculaire.divisie30.1",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:4",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:11",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:28:lid:1",
         "uitgesloten": false
        }
       ]
      }
     },
     {
      "casus_id": "LB-06",
      "naam": "Rekeningafspraken",
      "niveau": "gemiddeld",
      "gebruik": "ontwikkeling",
      "verwachting": "concept",
      "route": "zoekvragen standaard (stap 8)",
      "maten": {
       "recall_nodig": {
        "teller": 2,
        "noemer": 7,
        "waarde": 0.286
       },
       "recall": {
        "teller": 2,
        "noemer": 7,
        "waarde": 0.286
       },
       "recall_exact": {
        "teller": 2,
        "noemer": 7,
        "waarde": 0.286
       },
       "precisie": {
        "teller": 2,
        "noemer": 40,
        "waarde": 0.05
       },
       "overlap": {
        "teller": 2,
        "noemer": 45,
        "waarde": 0.044
       }
      },
      "diagnose": {
       "uitgesloten_in_keuze": 0,
       "opname_onvolledig": 0
      },
      "categorieen": {
       "lex_mist": 5,
       "lex_onterecht": 38,
       "team_mist": 0,
       "twijfel": 0,
       "status": "voorstel van de code; de reviewer en de jurist volgen in LB2"
      },
      "verschillen": {
       "lex_mist": [
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:7a:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:25:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:4%3A89:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0019237:artikel:6:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0019237:artikel:6:lid:1",
         "rol": "kern",
         "plek": "onbekend"
        }
       ],
       "lex_onterecht": [
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:40ca:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0024096:artikel:7a.2",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:22:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:22:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:24a",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:25:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 0,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:31ter:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:34:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004766:id:BWBR0004766%2FHoofdstukIVA%2FArtikel40ca%2FLid1%2FOnderdeelc%2FSlottekst1",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:40ca:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:23:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:33:lid:6",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:22:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 1,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:22:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie7a%2FCirculaire.divisie7a.1",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:26:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:24:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:7a:lid:4",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:25:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:22:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:40ca:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 2,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:22:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:26b:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:22:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:40ca:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:22:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:40ca:lid:3",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:24a",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:25:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 3,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie7a%2FCirculaire.divisie7a.1",
         "uitgesloten": false
        },
        {
         "deelvraag": 4,
         "bron_iri": "urn:bwb:BWBR0004766:artikel:40ca:lid:1",
         "uitgesloten": false
        },
        {
         "deelvraag": 4,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie7a%2FCirculaire.divisie7a.1",
         "uitgesloten": false
        },
        {
         "deelvraag": 4,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:16",
         "uitgesloten": false
        },
        {
         "deelvraag": 4,
         "bron_iri": "urn:bwb:BWBR0005537:artikel:4%3A93:lid:4",
         "uitgesloten": false
        },
        {
         "deelvraag": 4,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:22:lid:7",
         "uitgesloten": false
        },
        {
         "deelvraag": 4,
         "bron_iri": "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie14%2FCirculaire.divisie14.4%2FCirculaire.divisie14.4.14",
         "uitgesloten": false
        },
        {
         "deelvraag": 4,
         "bron_iri": "urn:bwb:BWBR0004770:artikel:51:lid:2",
         "uitgesloten": false
        },
        {
         "deelvraag": 4,
         "bron_iri": "urn:bwb:BWBR0018472:artikel:45:lid:1",
         "uitgesloten": false
        }
       ]
      }
     }
    ],
    "per_niveau": [
     {
      "gebruik": "ontwikkeling",
      "niveau": "gemiddeld",
      "casussen": [
       "LB-03",
       "LB-04",
       "LB-05",
       "LB-06"
      ],
      "maten": {
       "recall_nodig": {
        "teller": 21,
        "noemer": 51,
        "waarde": 0.412
       },
       "recall": {
        "teller": 24,
        "noemer": 66,
        "waarde": 0.364
       },
       "recall_exact": {
        "teller": 22,
        "noemer": 66,
        "waarde": 0.333
       },
       "precisie": {
        "teller": 21,
        "noemer": 136,
        "waarde": 0.154
       },
       "overlap": {
        "teller": 24,
        "noemer": 181,
        "waarde": 0.133
       }
      },
      "categorieen": {
       "lex_mist": 42,
       "lex_onterecht": 115,
       "team_mist": 0,
       "twijfel": 0
      }
     },
     {
      "gebruik": "ontwikkeling",
      "niveau": "moeilijk",
      "casussen": [
       "LB-01",
       "LB-02"
      ],
      "maten": {
       "recall_nodig": {
        "teller": 8,
        "noemer": 37,
        "waarde": 0.216
       },
       "recall": {
        "teller": 8,
        "noemer": 42,
        "waarde": 0.19
       },
       "recall_exact": {
        "teller": 8,
        "noemer": 42,
        "waarde": 0.19
       },
       "precisie": {
        "teller": 8,
        "noemer": 56,
        "waarde": 0.143
       },
       "overlap": {
        "teller": 8,
        "noemer": 90,
        "waarde": 0.089
       }
      },
      "categorieen": {
       "lex_mist": 34,
       "lex_onterecht": 48,
       "team_mist": 0,
       "twijfel": 0
      }
     }
    ]
   }
  }
 ],
 "risicos": {
  "risicos": {
   "R01": {
    "risico": "De graaf is weg (lege repository na een herstart, `Repository inning doesn't exist`)",
    "impact": "hoog",
    "primair": 1,
    "tweede": 3,
    "per_laag": {
     "1": [
      "frontend/app/api/health/route.test.ts › [R01] geeft 503 bij een lege graaf: dan komt een straat niet groen door de uitrol",
      "frontend/app/api/health/route.test.ts › [R01] vraagt de diepe controle van api en graph-qa, en meldt database en graaf",
      "tools/graph-qa/tests/graaf/test_tools.py::test_ontbrekende_repository_krijgt_een_eigen_melding",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k1_annoteren_bij_een_lege_graaf_zegt_dat_de_wettekst_weg_is",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k2_een_afgebroken_beurt_laat_een_vrij_gesprek_en_een_vastgelegde_afbraak",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k3_een_fout_van_het_model_krijgt_een_eigen_melding",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k5_budget_op_bij_de_start_weigert_met_de_reden_en_start_niets",
      "tools/graph-qa/tests/runs/test_graafpeiling.py::test_de_peiling_onderscheidt_ok_leeg_en_onbereikbaar",
      "tools/graph-qa/tests/runs/test_graafpeiling.py::test_health_met_keten_meldt_de_graaf",
      "tools/graph-qa/tests/runs/test_graafpeiling.py::test_health_zonder_keten_raakt_de_graaf_niet"
     ],
     "4": [
      "docs/acceptatie/foutpaden.md"
     ]
    },
    "primair_gedekt": true
   },
   "R02": {
    "risico": "De api geeft een 5xx of is onbereikbaar",
    "impact": "hoog",
    "primair": 1,
    "tweede": 3,
    "per_laag": {
     "1": [
      "api/tests/test_health_keten.py::test_met_keten_en_een_database_die_faalt_503",
      "api/tests/test_health_keten.py::test_met_keten_en_een_werkende_database_ok",
      "api/tests/test_health_keten.py::test_zonder_keten_raakt_de_liveness_de_database_niet",
      "frontend/app/api/health/route.test.ts › [R02] geeft 503 als de database van de api niet antwoordt",
      "tools/graph-qa/tests/centrale_agent/test_agents.py::test_een_storing_van_de_api_is_een_zin_in_het_gesprek",
      "tools/graph-qa/tests/runs/test_api_herhaal.py::test_een_bericht_met_run_id_overleeft_een_tijdelijke_503",
      "tools/graph-qa/tests/runs/test_api_herhaal.py::test_een_inhoudelijke_fout_wordt_niet_herhaald",
      "tools/graph-qa/tests/runs/test_api_herhaal.py::test_zonder_sleutel_geen_herhaling"
     ]
    },
    "primair_gedekt": true
   },
   "R03": {
    "risico": "Een time-out: model, graaf, connector of api",
    "impact": "hoog",
    "primair": 1,
    "tweede": 3,
    "per_laag": {
     "1": [
      "frontend/app/api/_lib/proxy.test.ts › [R03] proxy – timeout"
     ],
     "4": [
      "docs/acceptatie/foutpaden.md"
     ]
    },
    "primair_gedekt": true
   },
   "R04": {
    "risico": "Een 400 van het model, en de strict-grens (een schema dat de API weigert)",
    "impact": "hoog",
    "primair": 1,
    "tweede": 2,
    "per_laag": {
     "1": [
      "tools/graph-qa/tests/context/test_llm_stap.py::test_een_fout_van_het_model_gaat_naar_de_aanroeper",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k1_annoteren_bij_een_lege_graaf_zegt_dat_de_wettekst_weg_is",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k2_een_afgebroken_beurt_laat_een_vrij_gesprek_en_een_vastgelegde_afbraak",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k3_een_fout_van_het_model_krijgt_een_eigen_melding",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k5_budget_op_bij_de_start_weigert_met_de_reden_en_start_niets"
     ],
     "2": [
      "tools/graph-qa/tests/context/test_strict_grenzen.py::test_de_delegatietools_zijn_niet_strict_en_de_code_toetst_hun_invoer",
      "tools/graph-qa/tests/context/test_strict_grenzen.py::test_de_strict_schemas_van_elk_profiel_passen_bij_de_api"
     ],
     "4": [
      "docs/acceptatie/foutpaden.md"
     ]
    },
    "primair_gedekt": true
   },
   "R05": {
    "risico": "Het budget is op (429 bij de start, het plafond in een run)",
    "impact": "middel",
    "primair": 1,
    "tweede": 3,
    "per_laag": {
     "1": [
      "tools/graph-qa/tests/begrippen/test_begrip_kaart.py::test_budget_op_start_geen_model",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k1_annoteren_bij_een_lege_graaf_zegt_dat_de_wettekst_weg_is",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k2_een_afgebroken_beurt_laat_een_vrij_gesprek_en_een_vastgelegde_afbraak",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k3_een_fout_van_het_model_krijgt_een_eigen_melding",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k5_budget_op_bij_de_start_weigert_met_de_reden_en_start_niets"
     ],
     "4": [
      "docs/acceptatie/foutpaden.md"
     ]
    },
    "primair_gedekt": true
   },
   "R06": {
    "risico": "Ongeldige invoer: een verkeerde IRI, een artikelnummer met een dubbele punt, een lege vraag, te groot, verkeerd schema",
    "impact": "middel",
    "primair": 1,
    "tweede": 2,
    "per_laag": {},
    "primair_gedekt": false
   },
   "R07": {
    "risico": "Gelijktijdigheid en 412's: twee juristen op dezelfde laag, een verouderde revisie, twee runs in één gesprek (409)",
    "impact": "hoog",
    "primair": 1,
    "tweede": 3,
    "per_laag": {
     "1": [
      "api/tests/test_annotatie_v2_postgres.py::test_compacte_elementen_laten_het_spoor_in_de_query_weg",
      "api/tests/test_annotatie_v2_postgres.py::test_concurrent_move_and_review_cannot_split_owner_or_history",
      "api/tests/test_annotatie_v2_postgres.py::test_concurrent_retry_commits_once",
      "api/tests/test_annotatie_v2_postgres.py::test_concurrent_same_node_revision_conflict_without_lost_update",
      "api/tests/test_annotatie_v2_postgres.py::test_detectiebijdragen_en_afwijzingen_overleven_postgres_roundtrip",
      "api/tests/test_annotatie_v2_postgres.py::test_een_relatievoorstel_en_dezelfde_relatie_van_de_jurist_tegelijk_geven_een_rij",
      "api/tests/test_annotatie_v2_postgres.py::test_twee_relaties_op_dezelfde_drager_tegelijk_geven_een_412_en_geen_verloren_revisie",
      "api/tests/test_races_postgres.py::test_een_deelvraag_daarna_nog_bijzetten_kan_op_de_nieuwe_revisie",
      "api/tests/test_races_postgres.py::test_een_gebruiker_start_tegelijk_twee_subagents_een_409",
      "api/tests/test_races_postgres.py::test_tegengestelde_besluiten_over_een_kandidaat_geven_nooit_een_dubbele_stand",
      "api/tests/test_races_postgres.py::test_twee_juristen_starten_tegelijk_een_regie_in_een_werkgebied_een_409",
      "api/tests/test_races_postgres.py::test_twee_keer_tegelijk_een_deelvraag_erbij_een_412",
      "api/tests/test_races_postgres.py::test_twee_keer_tegelijk_openen_geeft_een_voortgang",
      "api/tests/test_races_postgres.py::test_uitsluiten_dat_zijn_toets_las_voor_een_opnemen_weigert_onder_het_slot",
      "api/tests/test_races_postgres_verbruik_werkplaats.py::test_dezelfde_beurt_tegelijk_boeken_telt_een_keer",
      "api/tests/test_races_postgres_verbruik_werkplaats.py::test_twee_nieuwe_versies_op_dezelfde_voorganger_een_409",
      "api/tests/test_werkgebieden_postgres.py::test_dezelfde_bron_gelijktijdig_toevoegen_levert_een_selectie",
      "api/tests/test_werkgebieden_postgres.py::test_twee_gelijktijdige_wijzigingen_precies_een_412",
      "api/tests/test_werkgebieden_postgres.py::test_twee_kandidaten_gelijktijdig_opnemen_op_dezelfde_revisie_precies_een_412"
     ],
     "4": [
      "docs/acceptatie/foutpaden.md"
     ]
    },
    "primair_gedekt": true
   },
   "R08": {
    "risico": "Afbreken en hervatten: stoppen midden in een beurt, een herladen pagina, een hervatte subagent",
    "impact": "middel",
    "primair": 1,
    "tweede": 3,
    "per_laag": {
     "1": [
      "frontend/lib/useBeurt.dom.test.ts › useBeurt [R08]",
      "frontend/lib/useOnbewaardBewaker.dom.test.ts › useOnbewaardBewaker [R08]",
      "frontend/scripts/test-beurtuitkomst.mjs",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k1_annoteren_bij_een_lege_graaf_zegt_dat_de_wettekst_weg_is",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k2_een_afgebroken_beurt_laat_een_vrij_gesprek_en_een_vastgelegde_afbraak",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k3_een_fout_van_het_model_krijgt_een_eigen_melding",
      "tools/graph-qa/tests/runs/test_foutpaden_keten.py::test_k5_budget_op_bij_de_start_weigert_met_de_reden_en_start_niets",
      "tools/graph-qa/tests/runs/test_runs.py::test_stoppen_is_een_verzoek_geen_annulering"
     ],
     "4": [
      "docs/acceptatie/foutpaden.md"
     ]
    },
    "primair_gedekt": true
   },
   "R09": {
    "risico": "Een subagent rondt niet af (rapport `niet_gelukt`, geen rapport, de grens van het aantal rondes bereikt)",
    "impact": "hoog",
    "primair": 1,
    "tweede": 5,
    "per_laag": {
     "1": [
      "tools/graph-qa/tests/centrale_agent/test_delegatie_afsluiten.py::test_alleen_een_subagent_heeft_een_laatste_ronde_en_een_plafond",
      "tools/graph-qa/tests/centrale_agent/test_delegatie_afsluiten.py::test_als_subsjabloon_toont_de_uitleg_de_wettekst_en_laat_de_foute_aanwijzing_weg",
      "tools/graph-qa/tests/centrale_agent/test_delegatie_afsluiten.py::test_de_correctieronde_na_een_grote_beurt_krijgt_de_hele_beurt",
      "tools/graph-qa/tests/centrale_agent/test_delegatie_afsluiten.py::test_de_grenzen_komen_van_het_profiel_en_anders_van_het_platform",
      "tools/graph-qa/tests/centrale_agent/test_delegatie_afsluiten.py::test_de_laatste_ronde_zegt_de_code_en_het_kind_rondt_af_met_het_rapport",
      "tools/graph-qa/tests/centrale_agent/test_delegatie_afsluiten.py::test_de_weigering_gaat_door_tools_node_en_het_rapport_zegt_het_vooraf",
      "tools/graph-qa/tests/centrale_agent/test_delegatie_afsluiten.py::test_een_aanwijzing_in_extern_die_niet_klopt_valt_weg_naast_een_die_klopt",
      "tools/graph-qa/tests/centrale_agent/test_delegatie_afsluiten.py::test_een_uitleg_met_een_passage_die_niet_te_tonen_is_toont_de_andere_en_zegt_het",
      "tools/graph-qa/tests/centrale_agent/test_delegatie_afsluiten.py::test_het_plafond_gaat_vooraf_af_op_een_schatting_van_de_volgende_ronde",
      "tools/graph-qa/tests/centrale_agent/test_delegatie_afsluiten.py::test_het_platform_begrenst_wat_een_profiel_mag_vragen",
      "tools/graph-qa/tests/centrale_agent/test_delegatie_afsluiten.py::test_leest_het_kind_in_zijn_laatste_ronde_toch_door_dan_sluit_de_code_af_met_wat_hij_las",
      "tools/graph-qa/tests/centrale_agent/test_delegatie_afsluiten.py::test_na_een_subagent_die_niet_afrondde_leest_de_centrale_agent_niet_zelf_opnieuw",
      "tools/graph-qa/tests/centrale_agent/test_delegatie_afsluiten.py::test_over_het_plafond_of_na_de_laatste_ronde_komt_er_geen_modelronde_meer",
      "tools/graph-qa/tests/centrale_agent/test_delegatie_afsluiten.py::test_zonder_iets_te_tonen_weigert_de_uitleg_zoals_altijd"
     ],
     "4": [
      "docs/acceptatie/foutpaden.md"
     ]
    },
    "primair_gedekt": true
   },
   "R10": {
    "risico": "Lege of afgekapte resultaten (0 treffers, een bepaling zonder eigen tekst, afkapping op 40.000 tekens)",
    "impact": "hoog",
    "primair": 1,
    "tweede": 5,
    "per_laag": {
     "1": [
      "tools/graph-qa/tests/graaf/test_resultaatcontract.py::test_contract",
      "tools/graph-qa/tests/graaf/test_resultaatcontract.py::test_contract_van_een_connectortool",
      "tools/graph-qa/tests/graaf/test_resultaatcontract.py::test_een_ondeelbare_eenheid_boven_de_begroting_wordt_een_fout_geen_inkorting",
      "tools/graph-qa/tests/graaf/test_resultaatcontract.py::test_elke_connector_heeft_een_nepbron_en_elke_connectortool_argumenten",
      "tools/graph-qa/tests/graaf/test_resultaatcontract.py::test_elke_graaftool_heeft_testargumenten",
      "tools/graph-qa/tests/graaf/test_resultaatcontract.py::test_minder_rijen_dan_aantal_door_de_begroting_staat_in_de_toelichting",
      "tools/graph-qa/tests/graaf/test_resultaatcontract.py::test_openen_van_een_connectortool_haalt_hetzelfde_contract",
      "tools/graph-qa/tests/graaf/test_resultaatcontract.py::test_raw_sparql_bedenkt_geen_waarden",
      "tools/graph-qa/tests/graaf/test_resultaatcontract.py::test_raw_sparql_is_streng_en_geeft_nooit_een_half_antwoord",
      "tools/graph-qa/tests/graaf/test_resultaatcontract.py::test_raw_sparql_laat_terechte_query_door",
      "tools/graph-qa/tests/graaf/test_resultaatcontract.py::test_rijen_en_stuk_dragen_de_metadatasleutels"
     ]
    },
    "primair_gedekt": true
   },
   "R11": {
    "risico": "Verouderde bronnen: een andere wetsversie, een veranderde dragende passage, een opname die niet meer klopt",
    "impact": "hoog",
    "primair": 1,
    "tweede": 5,
    "per_laag": {},
    "primair_gedekt": false
   },
   "R12": {
    "risico": "Rechten en identiteit: `X-User-Id`, rol analist of beheerder, gesprekken per gebruiker, het admin-token, 2FA voor beheer",
    "impact": "hoog",
    "primair": 1,
    "tweede": 3,
    "per_laag": {
     "1": [
      "api/tests/test_rechtentabel.py::test_de_tabel_klopt_met_de_routes",
      "api/tests/test_rechtentabel.py::test_elk_domein_met_gebruikersgegevens_vraagt_een_actieve_gebruiker",
      "api/tests/test_rechtentabel.py::test_elke_route_buiten_gezondheid_vraagt_precies_een_token",
      "api/tests/test_rechtentabel.py::test_het_beheer_vraagt_het_admin_token_en_2fa_alleen_een_beheerder",
      "frontend/app/api/annotatie/run/route.test.ts › [R12] GET /api/annotatie/run – lezen alleen als eigenaar",
      "frontend/app/api/annotatie/run/route.test.ts › [R12] POST /api/annotatie/run – de eigenaarscontrole"
     ],
     "2": [
      "tests/poort/test_projectie_graphdb.py::test_de_projectiejob_hangt_aan_acceptatie_en_draait_alleen_na_de_merge",
      "tests/poort/test_projectie_graphdb.py::test_de_vormtoets_ziet_een_pr_trigger",
      "tests/poort/test_projectie_graphdb.py::test_geen_workflow_met_het_secret_draait_op_een_pull_request",
      "tests/poort/test_projectie_graphdb.py::test_graphdb_draait_in_dezelfde_versie_als_de_straten",
      "tests/poort/test_projectie_graphdb.py::test_het_secret_staat_alleen_in_de_uitrol_en_de_projectiejob"
     ],
     "3": [
      ".github/workflows/acceptatie-keten.yml"
     ],
     "4": [
      "docs/acceptatie/foutpaden.md"
     ]
    },
    "primair_gedekt": true
   },
   "R13": {
    "risico": "Prompt-injectie via de inhoud van een bron (wettekst, een uitspraak of een kamerstuk met een instructie erin)",
    "impact": "hoog",
    "primair": 1,
    "tweede": 5,
    "per_laag": {
     "1": [
      "api/tests/test_graaf_projectie_v2.py::test_elk_filter_van_zoek_query_is_ingedeeld",
      "api/tests/test_graaf_projectie_v2.py::test_source_iri_injection_rejected",
      "api/tests/test_graaf_projectie_v2.py::test_tekst_van_buiten_verandert_de_query_niet",
      "tools/graph-qa/tests/grounding/test_injectie_via_bron.py::test_een_stuk_uit_een_connector_blijft_een_gegeven",
      "tools/graph-qa/tests/grounding/test_injectie_via_bron.py::test_elke_connector_met_een_leestool_doet_mee",
      "tools/graph-qa/tests/grounding/test_injectie_via_bron.py::test_wettekst_uit_de_graaf_blijft_een_gegeven"
     ]
    },
    "primair_gedekt": true
   },
   "R14": {
    "risico": "Een connector staat uit of is onbekend",
    "impact": "middel",
    "primair": 1,
    "tweede": 2,
    "per_laag": {
     "1": [
      "tools/graph-qa/tests/connectors/test_bronschakelaar.py::test_chatrequest_kent_alleen_bekende_connectors",
      "tools/graph-qa/tests/connectors/test_bronschakelaar.py::test_chatrequest_kent_de_herkomst",
      "tools/graph-qa/tests/connectors/test_bronschakelaar.py::test_connector_literal_is_het_register",
      "tools/graph-qa/tests/connectors/test_bronschakelaar.py::test_de_beurt_meldt_haar_bronstand_en_de_meting_leest_hem",
      "tools/graph-qa/tests/connectors/test_bronschakelaar.py::test_de_reden_zegt_wie_hem_aanzet",
      "tools/graph-qa/tests/connectors/test_bronschakelaar.py::test_dispatch_weigert_een_uitgezette_bron_ook_in_code",
      "tools/graph-qa/tests/connectors/test_bronschakelaar.py::test_een_regel",
      "tools/graph-qa/tests/connectors/test_bronschakelaar.py::test_het_model_krijgt_een_uitgezette_bron_niet_aangeboden",
      "tools/graph-qa/tests/connectors/test_bronschakelaar.py::test_het_register_van_de_api_kent_dezelfde_connectors",
      "tools/graph-qa/tests/connectors/test_bronschakelaar.py::test_het_register_van_de_beheerder_begrenst",
      "tools/graph-qa/tests/connectors/test_bronschakelaar.py::test_zonder_connector_in_de_straat_geen_bronstand_event",
      "tools/graph-qa/tests/connectors/test_bronschakelaar.py::test_zonder_connector_in_de_straat_geen_registervraag"
     ],
     "4": [
      "docs/acceptatie/foutpaden.md"
     ]
    },
    "primair_gedekt": true
   },
   "R15": {
    "risico": "Brongetrouwheid: een citaat dat niet letterlijk is, een verkeerd anker, een vindplaats die niet klopt",
    "impact": "hoog",
    "primair": 1,
    "tweede": 5,
    "per_laag": {
     "1": [
      "tools/graph-qa/tests/evals/test_lex_bench.py::test_de_scorekaart_rekent_met_de_tellingen_van_de_set",
      "tools/graph-qa/tests/evals/test_lex_bench.py::test_een_blinde_casus_geeft_geen_bepalingen_prijs",
      "tools/graph-qa/tests/evals/test_lex_bench.py::test_een_maat_draagt_teller_en_noemer",
      "tools/graph-qa/tests/evals/test_lex_bench.py::test_een_meetmap_wordt_niet_overschreven",
      "tools/graph-qa/tests/evals/test_lex_bench.py::test_het_dashboard_laat_de_bepalingen_van_een_blinde_casus_weg",
      "tools/graph-qa/tests/evals/test_lex_bench.py::test_het_manifest_klopt_met_de_sets_van_nu",
      "tools/graph-qa/tests/evals/test_lex_bench.py::test_het_rapport_houdt_blind_en_ontwikkeling_apart_en_heeft_geen_totaal",
      "tools/graph-qa/tests/evals/test_lex_bench_review.py::test_de_opdracht_noemt_de_verschillen_en_niet_de_coordinator",
      "tools/graph-qa/tests/evals/test_lex_bench_review.py::test_de_tegenlezer_ziet_lex_niet",
      "tools/graph-qa/tests/evals/test_lex_bench_review.py::test_de_verschillen_zijn_genummerd_en_herhaalbaar",
      "tools/graph-qa/tests/evals/test_lex_bench_review.py::test_een_categorie_die_niet_bij_het_verschil_past_gaat_niet_door",
      "tools/graph-qa/tests/evals/test_lex_bench_review.py::test_een_review_volgens_de_voorstellen_klopt_en_telt",
      "tools/graph-qa/tests/evals/test_lex_bench_review.py::test_een_tegenlezing_hoort_bij_een_analist",
      "tools/graph-qa/tests/evals/test_lex_bench_review.py::test_een_tegenlezing_met_een_fout_gaat_niet_door",
      "tools/graph-qa/tests/evals/test_lex_bench_review.py::test_een_tegenlezing_zet_haar_bezwaren_in_onenig",
      "tools/graph-qa/tests/evals/test_lex_bench_review.py::test_team_mist_wordt_een_voorstel_voor_nagekomen_en_wijzigt_niets",
      "tools/graph-qa/tests/evals/test_lex_bench_review.py::test_tegen_de_eigen_verwachting_geeft_het_de_scorekaart_van_l1",
      "tools/graph-qa/tests/evals/test_lex_bench_team.py::test_bevriezen_schrijft_eenmalig_met_de_hash",
      "tools/graph-qa/tests/evals/test_lex_bench_team.py::test_de_cli_geeft_een_fout_als_exitcode",
      "tools/graph-qa/tests/evals/test_lex_bench_team.py::test_de_opdracht_noemt_geen_bepaling_uit_de_verwachting",
      "tools/graph-qa/tests/evals/test_lex_bench_team.py::test_de_teamverwachting_heeft_de_vorm_van_schema_4",
      "tools/graph-qa/tests/evals/test_lex_bench_team.py::test_een_blinde_casus_bevriest_niet_in_de_repo",
      "tools/graph-qa/tests/evals/test_lex_bench_team.py::test_een_blinde_casus_komt_niet_uit_de_repo",
      "tools/graph-qa/tests/evals/test_lex_bench_team.py::test_een_formulier_met_een_fout_gaat_niet_door",
      "tools/graph-qa/tests/evals/test_lex_bench_team.py::test_een_goed_formulier_klopt",
      "tools/graph-qa/tests/evals/test_lex_bench_team.py::test_een_makkelijke_casus_met_een_analist_zet_zijn_twijfel_open",
      "tools/graph-qa/tests/evals/test_lex_bench_team.py::test_het_dossier_draagt_geen_verwachting",
      "tools/graph-qa/tests/evals/test_lex_bench_team.py::test_samenvoegen_legt_a_en_b_naast_elkaar_zonder_te_kiezen",
      "tools/graph-qa/tests/evals/test_lex_bench_team.py::test_samenvoegen_weigert_een_fout_formulier_of_twee_keer_dezelfde_analist",
      "tools/graph-qa/tests/grounding/test_controle_citaten.py::test_een_ontkenning_is_geen_claim_dat_alles_gelezen_is",
      "tools/graph-qa/tests/grounding/test_controle_citaten.py::test_een_verwijzing_in_een_citaat_is_geen_samenvatting_van_het_verwezen_stuk",
      "tools/graph-qa/tests/grounding/test_controle_citaten.py::test_het_citaat_zelf_blijft_getoetst_op_letterlijkheid"
     ],
     "2": [
      "tests/poort/test_lex_bench.py::test_de_hashes_kloppen_met_de_sets",
      "tests/poort/test_lex_bench.py::test_een_meetmap_staat_in_het_meetlogboek",
      "tests/poort/test_lex_bench.py::test_elke_meetmap_heeft_de_vorm_van_een_run",
      "tests/poort/test_lex_bench.py::test_het_dashboard_toont_precies_de_vastgelegde_runs",
      "tests/poort/test_lex_bench.py::test_het_manifest_heeft_de_vorm_van_plan_3_3",
      "tests/poort/test_lex_bench.py::test_het_schema_4_noemt_de_velden_van_plan_3_1",
      "tests/poort/test_lex_bench.py::test_verrekening_staat_niet_in_de_casusset",
      "tests/poort/test_lex_bench_dashboard.py::test_de_pagina_haalt_geen_code_van_buiten",
      "tests/poort/test_lex_bench_dashboard.py::test_de_tokens_zijn_die_van_de_frontend",
      "tests/poort/test_lex_bench_dashboard.py::test_het_beeldmerk_is_dat_van_lex",
      "tests/poort/test_lex_bench_team.py::test_een_bench_profiel_heeft_precies_zijn_allowlist",
      "tests/poort/test_lex_bench_team.py::test_het_formulier_en_de_briefing_staan_er"
     ]
    },
    "primair_gedekt": true
   },
   "R16": {
    "risico": "De verkeerde route, het verkeerde profiel of de verkeerde tools",
    "impact": "middel",
    "primair": 2,
    "tweede": 5,
    "per_laag": {
     "2": [
      "tools/graph-qa/tests/routes/test_routering.py::test_de_statusregels_van_de_routering_zijn_in_gebruikerstaal_en_dragen_hun_route",
      "tools/graph-qa/tests/routes/test_routering.py::test_een_dubbelzinnige_afkorting_wordt_een_vraag_terug_zonder_model",
      "tools/graph-qa/tests/routes/test_routering.py::test_een_genoemd_artikel_buiten_de_graaf_wordt_zonder_model_gelezen",
      "tools/graph-qa/tests/routes/test_routering.py::test_een_genoemd_id_van_een_uitgezette_bron_wordt_niet_gelezen",
      "tools/graph-qa/tests/routes/test_routering.py::test_een_genoemd_id_wordt_zonder_model_gelezen",
      "tools/graph-qa/tests/routes/test_routering.py::test_elke_rij_heeft_een_id_en_een_verwachting",
      "tools/graph-qa/tests/routes/test_routering.py::test_routering",
      "tools/graph-qa/tests/routes/test_routering.py::test_zonder_de_connector_geen_verzoek_naar_overheid"
     ]
    },
    "primair_gedekt": true
   },
   "R17": {
    "risico": "Methodes vermengd (JRM-taal of JAS-markeringen in de verkeerde methode)",
    "impact": "middel",
    "primair": 2,
    "tweede": 5,
    "per_laag": {
     "2": [
      "tools/graph-qa/tests/methode/test_methodes_gescheiden.py::test_de_jrm_verrijking_bestaat_niet_meer_in_wetsanalyse",
      "tools/graph-qa/tests/methode/test_methodes_gescheiden.py::test_de_skill_wetsanalyse_noemt_het_jrm_alleen_als_verwijzing",
      "tools/graph-qa/tests/methode/test_methodes_gescheiden.py::test_de_toets_vindt_een_vermenging",
      "tools/graph-qa/tests/methode/test_methodes_gescheiden.py::test_elke_uitzondering_bestaat_nog",
      "tools/graph-qa/tests/methode/test_methodes_gescheiden.py::test_het_dossier_van_wetsanalyse_kent_geen_scenario_of_gevolg_als_identiteit",
      "tools/graph-qa/tests/methode/test_methodes_gescheiden.py::test_het_label_is_wetsanalyse_jas"
     ]
    },
    "primair_gedekt": true
   },
   "R18": {
    "risico": "Een uitrol die niet draait (de revisie crasht, een verkeerde digest, een ontbrekend secret)",
    "impact": "hoog",
    "primair": 3,
    "tweede": null,
    "per_laag": {
     "2": [
      "tests/poort/test_uitrolpoort.py::test_de_health_route_kent_de_ketenstand",
      "tests/poort/test_uitrolpoort.py::test_de_poort_wordt_gebruikt",
      "tests/poort/test_uitrolpoort.py::test_elk_gebruik_heeft_een_checkout_en_de_rooktest",
      "tests/poort/test_uitrolpoort.py::test_geen_eigen_kopie_van_de_poortlus",
      "tests/poort/test_uitrolpoort.py::test_scaled_to_zero_telt_als_gezond",
      "tests/poort/test_uitrolpoort.py::test_wie_uitrolt_gebruikt_de_poort"
     ],
     "3": [
      ".github/workflows/acceptatie-keten.yml"
     ],
     "4": [
      "docs/acceptatie/foutpaden.md"
     ]
    },
    "primair_gedekt": true
   },
   "R19": {
    "risico": "Een gedeeld account: verbruik en besluiten van twee sessies door elkaar, een bulkactie die andermans werk raakt",
    "impact": "hoog",
    "primair": 3,
    "tweede": 4,
    "per_laag": {
     "1": [
      "tools/wetsanalyse-acceptatie-mcp/src/keten.test.ts › [R19] een mislukte stap ruimt alleen op wat de run maakte, en is nooit groen",
      "tools/wetsanalyse-acceptatie-mcp/src/keten.test.ts › [R19] het ketenscenario maakt, leest en ruimt alleen zijn eigen objecten op",
      "tools/wetsanalyse-acceptatie-mcp/src/runruimte.test.ts › [R19] de vangrail: alleen de eigen ruimte van een testrun",
      "tools/wetsanalyse-acceptatie-mcp/src/runruimte.test.ts › [R19] opruimplan: de run, met deelgesprekken vóór hun ouder, en niets van een ander",
      "tools/wetsanalyse-acceptatie-mcp/src/runruimte.test.ts › [R19] uitvoeren: gesprekken eerst, werkgebied met zijn revisie, en de vangrail toetst elk",
      "tools/wetsanalyse-acceptatie-mcp/src/runruimte.test.ts › [R19] verwijderend: een DELETE of een route die op verwijderen eindigt; lezen niet"
     ],
     "2": [
      "tests/poort/test_acceptatie_keten.py::test_geen_hostnaam_en_de_url_gemaskeerd",
      "tests/poort/test_acceptatie_keten.py::test_het_scenario_werkt_onder_een_eigen_voorvoegsel_dat_de_vangrail_kent",
      "tests/poort/test_acceptatie_keten.py::test_het_token_staat_alleen_in_de_ketenworkflow",
      "tests/poort/test_acceptatie_keten.py::test_nooit_op_een_pull_request",
      "tests/poort/test_acceptatie_keten.py::test_zonder_token_overgeslagen_en_niet_groen"
     ],
     "3": [
      ".github/workflows/acceptatie-keten.yml"
     ],
     "4": [
      "docs/acceptatie/foutpaden.md",
      "docs/acceptatie/testaccount.md"
     ]
    },
    "primair_gedekt": true
   },
   "R20": {
    "risico": "De projectie in de graaf wijkt af van Postgres",
    "impact": "hoog",
    "primair": 1,
    "tweede": 3,
    "per_laag": {
     "1": [
      "api/tests/test_projector_v2_integration.py::test_commit_staat_direct_in_de_graaf_zonder_de_lus",
      "api/tests/test_projector_v2_integration.py::test_een_hangende_graaf_blokkeert_geen_besluit_en_de_projectie_haalt_hem_in",
      "api/tests/test_projector_v2_integration.py::test_orphans_removed_but_existing_and_foreign_graphs_preserved",
      "api/tests/test_projector_v2_integration.py::test_partial_http_failure_retry_and_repository_recovery"
     ],
     "3": [
      ".github/workflows/projectie-graphdb.yml"
     ]
    },
    "primair_gedekt": true
   },
   "R21": {
    "risico": "Een nepdienst die niet op de echte dienst lijkt (vorm van een antwoord, de SSE-framing, één antwoord op elke query)",
    "impact": "hoog",
    "primair": 2,
    "tweede": 1,
    "per_laag": {
     "1": [
      "frontend/app/nepApi.test.ts › [R21] de nep-api van de browserscripts",
      "frontend/scripts/test-beurtuitkomst.mjs"
     ],
     "2": [
      "api/tests/test_naad_minicasus.py::test_de_minicasus_loopt_door_elke_naad_van_de_api",
      "tests/poort/test_risicomatrix.py::test_de_matrix_meldt_een_onbekend_risico_en_telt_per_laag",
      "tests/poort/test_risicomatrix.py::test_elke_marker_noemt_een_bekend_risico",
      "tests/poort/test_risicomatrix.py::test_het_register_is_goed_gevormd",
      "tools/graph-qa/tests/evals/test_fakes_streng.py::test_een_aangeboden_tool_en_een_bewuste_uitzondering_gaan_door",
      "tools/graph-qa/tests/evals/test_fakes_streng.py::test_een_ronde_te_veel_zegt_wat_er_gevraagd_werd",
      "tools/graph-qa/tests/evals/test_fakes_streng.py::test_een_tool_die_niet_werd_aangeboden_is_een_fout",
      "tools/graph-qa/tests/evals/test_procestoestand.py::test_de_zoektocht_herkent_de_vormen",
      "tools/graph-qa/tests/evals/test_procestoestand.py::test_elke_module_met_procesbrede_toestand_meldt_zich",
      "tools/graph-qa/tests/evals/test_procestoestand.py::test_reset_maakt_de_regelingen_leeg",
      "tools/graph-qa/tests/runs/test_naad_minicasus.py::test_de_batch_draagt_wat_de_api_nodig_heeft",
      "tools/graph-qa/tests/runs/test_naad_minicasus.py::test_de_batch_van_graph_qa_is_het_gedeelde_voorbeeld"
     ]
    },
    "primair_gedekt": true
   },
   "R22": {
    "risico": "Toegankelijkheid en touch",
    "impact": "middel",
    "primair": 1,
    "tweede": 4,
    "per_laag": {},
    "primair_gedekt": false
   },
   "R23": {
    "risico": "Een controle die fail-open is (de GOK-controle van `id_herkomst` staat uit met een lege namenlijst, bijvoorbeeld vlak na een herstart van GraphDB)",
    "impact": "middel",
    "primair": 1,
    "tweede": null,
    "per_laag": {},
    "primair_gedekt": false
   }
  },
  "onbekend": [],
  "niet_gedekt_hoog": [
   "R11"
  ]
 }
};
