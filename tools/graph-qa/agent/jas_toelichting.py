# Gegenereerd uit .claude/skills/wetsanalyse/references/jas-klassen-referentie.md door
# scripts/genereer_jas_klassen.py; niet met de hand bewerken. Alleen voor `jas_klasse_opvragen`.
TOELICHTING: dict[str, dict[str, object]] = {'Rechtssubject': {'samenhang': 'Een rechtssubject is partij in een of meer rechtsbetrekkingen, verricht een '
                                'rechtsfeit of ondervindt de gevolgen ervan, en kan eigenaar of houder van een '
                                'rechtsobject zijn. In de catalogus: rechthebbende, plichthebbende, verricht, '
                                'bevoegde.',
                   'afbakening': ['Rechtsobject — beide zijn een naamwoordgroep. De toets is de functie: draagt het '
                                  'een recht of plicht (subject), of gaat het recht of de plicht erover (object)? Ook '
                                  'een persoon kan voorwerp zijn.',
                                  'Variabele en variabelewaarde — een kenmerk van een persoon ("gehuwd", "ouder dan '
                                  '18") is een variabele, niet een tweede subject. Markeer het subject en het kenmerk '
                                  'apart als beide een functie dragen.',
                                  'Plaatsaanduiding — "de gemeente" is een subject als zij handelt of iets moet, en '
                                  'een plaats als zij een gebied aanwijst.']},
 'Rechtsobject': {'samenhang': 'Een rechtsobject is het voorwerp van een rechtsbetrekking of rechtsfeit, en heeft '
                               'kenmerken met een waarde (het loon bij een dienstbetrekking). In de catalogus: '
                               'voorwerp, kenmerk, onderdeel.',
                  'afbakening': ['Rechtssubject — zie daar: de functie beslist, niet het woord.',
                                 'Variabele en variabelewaarde — een bedrag of toeslag is voorwerp als het recht of de '
                                 'plicht erover gaat ("recht op een toeslag"), en een variabele als het een kenmerk '
                                 'met een waarde is ("de hoogte van de toeslag").',
                                 'Rechtsfeit — een handeling als zelfstandig naamwoord ("de betaling") is voorwerp als '
                                 'de norm erover gaat, en rechtsfeit als zij de juridische toestand verandert.']},
 'Rechtsbetrekking': {'subklassen': 'Het boek onderscheidt vier soorten, naar Hohfeld. Noem een soort alleen als de '
                                    'tekst haar draagt; een markering krijgt er geen eigen label voor. Aanspraak '
                                    'tegenover verplichting — de ene partij moet iets doen of laten, de andere kan '
                                    'daarop aanspraak maken. Dit is de meest voorkomende soort. Drie varianten, naar '
                                    'wat er kan als de verplichting niet wordt nagekomen: direct af te dwingen; pas af '
                                    'te dwingen na een ingebrekestelling of aanmaning; of niet af te dwingen. Of '
                                    'nakoming af te dwingen is, staat vaak in een andere bepaling: één passage zonder '
                                    'sanctie maakt een verplichting niet zwak. Bevoegdheid tegenover gehoudenheid — de '
                                    'ene partij kan een rechtshandeling verrichten, de andere is daaraan onderworpen. '
                                    'Gebonden: de bevoegdheid moet worden uitgeoefend als aan de voorwaarden is '
                                    'voldaan; te herkennen aan de tegenwoordige tijd ("kent toe", "neemt het '
                                    'besluit"). Discretionair: er is ruimte om haar wel of niet uit te oefenen, of om '
                                    'af te wegen; te herkennen aan "kan", "naar zijn oordeel", "naar zijn mening" (M01 '
                                    'h.4 §4.2.2). Immuniteit tegenover geen bevoegdheid — een partij is gevrijwaard '
                                    'van de bevoegdheid van een ander. Lastig te onderscheiden van een bevoegdheid '
                                    'onder een voorwaarde: een termijn waarna een bevoegdheid vervalt, is een '
                                    'voorwaarde in de tijd, geen immuniteit. Laat een onderbouwde immuniteit staan. '
                                    'Vrijheid tegenover geen aanspraak — een partij mag kiezen, en een ander kan daar '
                                    'niets tegen inbrengen. Hier horen geen rechtsfeiten bij.',
                      'samenhang': 'Een rechtsbetrekking heeft altijd twee partijen en een voorwerp, vaak een duur, en '
                                   'ontstaat, wijzigt of eindigt door een rechtsfeit. Loop bij elke rechtsbetrekking '
                                   'na: wie is rechthebbende, wie plichthebbende, wat is het voorwerp, welke '
                                   'voorwaarden gelden, en hoe lang geldt zij? Noemt de tekst een partij niet, zie dan '
                                   '[relaties](relaties.md). In de catalogus: rechthebbende, plichthebbende, voorwerp, '
                                   'voorwaarde, tijd, en vanuit het rechtsfeit creeert, wijzigt, beeindigt.',
                      'afbakening': ['Rechtsfeit — zie het onderscheid hieronder bij §4: toestand tegenover '
                                     'verandering. "Mag oversteken" is de norm; het oversteken zelf is een handeling.',
                                     'Afleidingsregel — "is … verschuldigd" kan een plicht uitdrukken of de uitkomst '
                                     'van een berekening inleiden. Staat er hoe het bedrag wordt bepaald, dan is dat '
                                     'deel de afleidingsregel; de plicht om te betalen blijft de rechtsbetrekking.',
                                     'Delegatiebevoegdheid en delegatie-invulling — "kunnen regels worden gesteld" is '
                                     'een bevoegdheid, maar de meer specifieke klasse gaat voor: delegatie.']},
 'Rechtsfeit': {'subklassen': 'Vier soorten. Noem een soort alleen als de tekst haar draagt. Rechtshandeling — een '
                              'handeling die op het rechtsgevolg gericht is (een bezwaarschrift indienen, een besluit '
                              'nemen). Niet elke handeling is een rechtshandeling: controleer of het gevolg beoogd is '
                              'en of de wet het eraan verbindt. Feitelijke handeling met rechtsgevolg — het gevolg '
                              'treedt in zonder dat het beoogd was (schade veroorzaken). Gebeurtenis met rechtsgevolg '
                              '— niemand handelt (een overlijden). Tijdsverloop met rechtsgevolg — een termijn '
                              'verstrijkt en daardoor verandert er iets.',
                'samenhang': 'Een rechtsfeit werkt altijd op een rechtsbetrekking (het creëert, wijzigt of beëindigt '
                             'haar), heeft een voorwerp, en hangt aan een tijdstip of periode. Een handeling heeft '
                             'bovendien een subject dat haar verricht. Loop na: welke rechtsbetrekking raakt het, wie '
                             'verricht het, wat is het voorwerp, en wanneer? Vind je geen rechtsbetrekking waarop het '
                             'werkt, dan is het waarschijnlijk geen rechtsfeit. In de catalogus: creeert, wijzigt, '
                             'beeindigt, verricht, voorwerp, tijd.',
                'afbakening': ['Voorwaarde — dezelfde handeling kan rechtsfeit zijn (zij verandert de toestand) of een '
                               'eis voor een gevolg ("indien hij betaalt"). In een voorwaardelijke bijzin is zij een '
                               'voorwaarde; de handeling daarbinnen kan daarnaast een eigen markering krijgen als zij '
                               'elders als rechtsfeit werkt.',
                               'Tijdsaanduiding — "het verstrijken van de termijn" is tijdsverloop met rechtsgevolg; '
                               '"zes weken na de dagtekening" is de tijdsaanduiding. De startgebeurtenis in een '
                               'termijn hoort bij de tijdsaanduiding.',
                               'Rechtsobject — een handeling als zelfstandig naamwoord is voorwerp als de norm erover '
                               'gaat. Heeft zij een eigen voorwerp ("het indienen van een bezwaarschrift"), dan is dat '
                               'voorwerp het rechtsobject.']},
 'Voorwaarde': {'samenhang': 'Een voorwaarde hoort bij een rechtsfeit, rechtsbetrekking, rechtssubject of '
                             'rechtsobject, of is deel van een afleidingsregel. Een voorwaarde zonder iets waarop zij '
                             'werkt, is onvolledig. Wat zij vergelijkt, is haar invoer. In de catalogus: voorwaarde, '
                             'invoer, operator_in.',
                'afbakening': ['Rechtsfeit — zie §4: een handeling als eis is een voorwaarde.',
                               'Operator — de vergelijking binnen de voorwaarde ("meer bedraagt dan") is de operator; '
                               'de voorwaarde is het geheel.',
                               'Afleidingsregel — een regel die bepaalt óf een recht bestaat, is een beslisregel '
                               '(afleidingsregel) met voorwaarden erin. Een losse eis is alleen een voorwaarde.',
                               'Brondefinitie — een definitie bevat vaak eisen ("voor zover …"). Het geheel is de '
                               'brondefinitie; de eis daarin kan een eigen markering Voorwaarde krijgen.']},
 'Afleidingsregel': {'samenhang': 'Een afleidingsregel heeft altijd precies één uitvoer (een variabele, rechtssubject '
                                  'of rechtsobject), en invoer, operatoren en vaak voorwaarden. In de catalogus: '
                                  'uitvoer, invoer, operator_in, voorwaarde.',
                     'afbakening': ['Parameter en parameterwaarde — "bedraagt € 23" legt een waarde vast en is geen '
                                    'berekening: parameter. Pas met invoer en een bewerking is het een '
                                    'afleidingsregel.',
                                    'Rechtsbetrekking — zie §3: "is verschuldigd" als plicht of als uitkomst.',
                                    'Voorwaarde — een beslisregel bevat voorwaarden; de voorwaarden zijn deel van de '
                                    'regel, niet de regel.',
                                    'Operator — zie §9: de regel is het geheel, de operator het verbindende woord.']},
 'Variabele en variabelewaarde': {'samenhang': 'Een variabele is een kenmerk van een rechtssubject, rechtsobject, '
                                               'rechtsfeit of rechtsbetrekking; een variabelewaarde hoort bij een '
                                               'variabele. Kenmerken van een algemeen subject of object gelden ook '
                                               'voor de specialisaties ervan. Zoek bij elke variabele waar zij een '
                                               'kenmerk van is. In de catalogus: kenmerk, waarde, invoer, uitvoer.',
                                  'afbakening': ['Parameter en parameterwaarde — zie de toets hieronder bij §8: per '
                                                 'geval verschillend of voor iedereen gelijk.',
                                                 'Tijdsaanduiding en Plaatsaanduiding — de specifiekere klasse gaat '
                                                 'voor bij dezelfde functie (H2:107, H2:116).',
                                                 'Rechtsobject — zie §2: voorwerp van het recht of kenmerk met een '
                                                 'waarde.']},
 'Parameter en parameterwaarde': {'samenhang': 'Een parameter is invoer van een afleidingsregel of deel van een '
                                               'voorwaarde; een parameterwaarde geeft de parameter zijn waarde voor de '
                                               'periode waarin hij geldt. In de catalogus: invoer, waarde, tijd.',
                                  'afbakening': ['Variabele en variabelewaarde — zie de toets hierboven.',
                                                 'Tijdsaanduiding en Plaatsaanduiding — een vaste termijn of een vast '
                                                 'gebied is de specifiekere klasse (H2:107, H2:116); zie §10, '
                                                 'Verbijzondering.',
                                                 'Operator — "tweemaal" en "de helft van" drukken een bewerking uit: '
                                                 'de operator. Het getal daarin is geen eigen parameter, tenzij de '
                                                 'tekst het als waarde vastlegt.']},
 'Operator': {'samenhang': 'Een operator hoort bij de afleidingsregel of voorwaarde waarin hij staat, en verbindt '
                           'operanden. De volgorde van de operanden telt bij aftrekken en vergelijken. In de '
                           'catalogus: operator_in, operand.',
              'afbakening': ['Afleidingsregel — zie de samenloop hierboven.',
                             'Voorwaarde — de vergelijking is de operator, de hele eis de voorwaarde. Een voegwoord '
                             'dat een voorwaarde inleidt ("indien", "tenzij") is geen operator; "en" tussen twee '
                             'woorden van één naamwoordgroep ook niet.']},
 'Tijdsaanduiding': {'samenhang': 'Een tijdsaanduiding neemt de verbanden over van de klasse die zij verbijzondert: '
                                  'als parameter is zij invoer van een regel of deel van een voorwaarde, als variabele '
                                  'een kenmerk. Daarnaast zegt zij wanneer een rechtsbetrekking geldt of een '
                                  'rechtsfeit plaatsvindt. In de catalogus: tijd, en via de verbijzondering invoer, '
                                  'operand, waarde.',
                     'afbakening': ['Variabele en variabelewaarde, Parameter en parameterwaarde — de prioriteitsregel '
                                    'hierboven.',
                                    'Rechtsfeit — de termijn is de tijdsaanduiding; dat zij verstrijkt en daardoor '
                                    'iets verandert, is het rechtsfeit. De startgebeurtenis ("na de dagtekening") '
                                    'hoort bij de tijdsaanduiding.']},
 'Plaatsaanduiding': {'samenhang': 'Net als de tijdsaanduiding neemt een plaatsaanduiding de verbanden over van de '
                                   'klasse die zij verbijzondert. Vaak is zij deel van een voorwaarde of bepaalt zij '
                                   'wie tot een groep hoort ("in Nederland wonen"). In de catalogus: plaats.',
                      'afbakening': ['Variabele en variabelewaarde, Parameter en parameterwaarde — de prioriteitsregel '
                                     'hierboven.',
                                     'Rechtssubject — "de gemeente" als bestuursorgaan is een subject, als gebied een '
                                     'plaats.']},
 'Delegatiebevoegdheid en delegatie-invulling': {'samenhang': 'Delegatiebevoegdheid en delegatie-invulling horen bij '
                                                              'elkaar, en de bevoegdheid komt toe aan een '
                                                              'rechtssubject (de regering, een minister). In de '
                                                              'catalogus: delegatie_over, bevoegde.',
                                                 'afbakening': ['Rechtsbetrekking — elke delegatie is een bevoegdheid, '
                                                                'maar de specifiekere klasse gaat voor. Een '
                                                                'bevoegdheid om iets anders te doen dan regels stellen '
                                                                '(een besluit nemen, uitstel verlenen) is een '
                                                                'rechtsbetrekking.']},
 'Brondefinitie': {'samenhang': 'Een brondefinitie hoort bij een term die voor een rechtssubject, rechtsobject, '
                                'variabele of parameter wordt gebruikt. De catalogus staat definieert ook toe naar een '
                                'rechtsbetrekking, rechtsfeit, tijds- of plaatsaanduiding: dat is ruimer dan het boek '
                                'en een projectkeuze (P18).',
                   'afbakening': ['Voorwaarde — de omschrijving bevat vaak eisen. Het geheel is de brondefinitie; een '
                                  'eis daarin kan een eigen markering krijgen.',
                                  'Rechtssubject — de gedefinieerde term kan een partij aanduiden. Markeer de '
                                  'definitie als brondefinitie en de term, waar hij in een norm voorkomt, als '
                                  'rechtssubject.']}}
