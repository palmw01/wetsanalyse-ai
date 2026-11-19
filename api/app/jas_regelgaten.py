# Gegenereerd uit .claude/skills/wetsanalyse/regelgaten.json; niet handmatig bewerken.
# Draai tools/graph-qa/scripts/genereer_regelgaten.py.
"""De gaten van een afleidingsregel (activiteit 3b): code, plek, herkomst en melding."""
from __future__ import annotations

#: De eerste twaalf tekens van de sha256 van de bron.
REGELGATEN_VERSIE = 'e3ffe980777f'

#: Waar een gat zit: het skelet, het regelobject of de keten.
PLEKKEN = ('skelet', 'regel', 'keten')

#: code → plek, herkomst en melding (met {velden} om in te vullen).
GATEN = {'uitvoer_ontbreekt': {'plek': 'skelet',
                       'herkomst': 'regelspecialist',
                       'melding': 'Er is geen uitvoer: welk begrip leidt deze regel af?'},
 'meer_uitvoeren': {'plek': 'skelet',
                    'herkomst': 'methode',
                    'melding': 'Deze formulering heeft {n} uitvoeren; een afleidingsregel heeft er precies '
                               'één. Draagt ze meer regels?'},
 'invoer_ontbreekt': {'plek': 'skelet', 'herkomst': 'regelspecialist', 'melding': 'Er is geen invoer.'},
 'invoer_zonder_volgorde': {'plek': 'skelet',
                            'herkomst': 'regelspecialist',
                            'melding': '{n} van de {m} invoeren hebben geen volgorde.'},
 'rechtsobject_als_invoer': {'plek': 'skelet',
                             'herkomst': 'regelspecialist',
                             'melding': 'De invoer is alleen een rechtsobject; een regel rekent met een '
                                        'waarde ervan (een variabele, parameter of tijdsaanduiding, met een '
                                        'relatie kenmerk naar het object).'},
 'voorwaarde_bij_andere_drager': {'plek': 'skelet',
                                  'herkomst': 'regelspecialist',
                                  'melding': 'Een voorwaarde in deze bepaling hangt aan een andere drager, '
                                             'niet aan deze regel. Geldt ze ook voor de regel?'},
 'afwijking_zonder_uitzondering': {'plek': 'skelet',
                                   'herkomst': 'regelspecialist',
                                   'melding': 'De bepaling zegt "in afwijking van", maar de regel heeft geen '
                                              'relatie uitzondering_op.'},
 'uitvoer_zonder_begrip': {'plek': 'regel',
                           'herkomst': 'regelspecialist',
                           'melding': 'De uitvoerformulering van de regel draagt geen begrip.'},
 'regelbegrip_zonder_bepalen': {'plek': 'regel',
                                'herkomst': 'methode',
                                'melding': 'Het regelbegrip heet niet "bepalen <uitvoer>".'},
 'parameter_zonder_tijdvak': {'plek': 'regel',
                              'herkomst': 'regelspecialist',
                              'melding': 'De parameter {naam} heeft geen waarde met een tijdvak.'},
 'parameterwaarde_in_definitie': {'plek': 'regel',
                                  'herkomst': 'methode',
                                  'melding': 'De definitie van de parameter {naam} noemt een waarde; de '
                                             'waarde is een eigen begrip in een tijdvak.'},
 'rust_op_contextbron': {'plek': 'regel',
                         'herkomst': 'methode',
                         'melding': 'De regel rust op een bron met de rol context ({bron}). Wordt dit een '
                                    'bron om te analyseren?'},
 'operator_zonder_begrip': {'plek': 'regel',
                            'herkomst': 'methode',
                            'melding': 'De operatorformulering "{tekst}" in de regel draagt geen '
                                       'operatorbegrip.'},
 'impliciete_invoer': {'plek': 'regel',
                       'herkomst': 'methode',
                       'melding': 'De invoer {naam} rust op geen formulering en geen regel leidt haar af. '
                                  'Een impliciete invoer: ontbrekend uitvoeringsbeleid?'},
 'zelfde_uitvoer': {'plek': 'keten',
                    'herkomst': 'regelspecialist',
                    'melding': 'Meer regels leiden hetzelfde begrip af: hun gevallen moeten elkaar '
                               'uitsluiten, of het is één regel met meer gevallen.'},
 'regelbegrip_meer_uitvoeren': {'plek': 'keten',
                                'herkomst': 'methode',
                                'melding': 'Eén regelbegrip hoort bij regels met verschillende uitvoeren; '
                                           'elke uitvoer heeft zijn eigen regel en regelbegrip.'}}


def gat(code: str, **waarden) -> dict:
    """Eén gat met zijn melding ingevuld: `{code, plek, tekst}`. Een onbekende code is een programmeerfout."""
    g = GATEN[code]
    return {"code": code, "plek": g["plek"], "tekst": g["melding"].format(**waarden)}
