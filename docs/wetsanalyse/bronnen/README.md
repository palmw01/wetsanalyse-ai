# Bewaarde bronnen

Het [manifest](manifest.json) legt per bron het bron-ID, de herkomst, de versie, de status en de
SHA-256 vast. De originelen staan lokaal in deze map of op hun eigen plek in de repo (het veld
`pad`). Hashes identificeren de bewaarde bytes; zij bewijzen geen juridische geldigheid.

De [skillbronverantwoording](../../../.claude/skills/wetsanalyse/references/bronnen.md)
verbindt instructies met precieze brononderdelen en benoemt eigen projectkeuzes.

Regels:

- **PDF's, HTML en `*.pages.md` staan niet in Git** (`.gitignore` hier en in de repo-wortel). Deze
  repo is publiek; een verse kloon heeft alleen deze README en het manifest.
- **Overschrijf een bewaard exemplaar niet.** Een nieuw exemplaar krijgt een nieuwe versie of
  raadpleegdatum en een eigen regel in het manifest.
- Bestaande bronpublicaties en hun licentievoorwaarden blijven ongewijzigd.

**JRM 2** staat lokaal als `jrm2-2024-11-18.pdf`, met een doorzoekbare extractie
`jrm2-2024-11-18.pages.md`. De versiedatum is die op de titelpagina (2024-11-18); de bestandsnaam
van de vindplaats noemt 2024-11-29. Beide vindplaatsen en hashes staan in het manifest. Bij
diagrammen is het origineel leidend.

De drie Staatsbladen (`omgevingswet-2016.pdf`, `bw6-1991.pdf`, `rvv-1990.pdf`) zijn historische
publicaties voor afgebakende tekstanalyse in de [referentieset](../referentieset/README.md), geen
geconsolideerde weergave van het huidige recht.
