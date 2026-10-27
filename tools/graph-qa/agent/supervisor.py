"""
Supervisor van de juridische agent (vervangt de vroegere QA-router).

De supervisor bepaalt per vraag WELKE worker-agents nodig zijn en in welke volgorde: `antwoord`
(vraag beantwoorden/duiden/definiëren, gegrond op de graaf) of `annotatie` (een artikel/lid volgens
het JAS markeren). Hij mag ketenen (bv. eerst annoteren, dan samenvatten). Retrieval (get_lid/
get_artikel) is een gedeelde tool die de gekozen worker zelf aanroept.

Sinds F3c (ADR-005) kiest hij ook de agents op een werkgebied – `deelvragen` en `begrippen` – met een
`TAAK:` uit een vaste lijst (`agents/register.py`); een klik op een suggestie (`actie`) kiest agent en taak
zonder model. `werkgebied` (samenstellen, of met `TAAK: aanvullen` het dossier van een bestaand werkgebied
aanvullen), `deelvragen` en `begrippen` ketenen met niets.

Backward-compatible met het oude router-formaat: een respons met alleen `SPECIALIST:`/`PLAN:` (zonder
`WORKERS:`) wordt gelezen als één `antwoord`-worker met die specialist – zo blijven de bestaande
QA-flows/tests ongewijzigd.
"""
from __future__ import annotations

SUPERVISOR_SYSTEM = (
    "Je bent de supervisor van een juridische agent over een kennisgraaf met Nederlandse wet- en "
    "regelgeving (invordering/belastingen). Bepaal welke agent(s) de vraag nodig heeft en in welke "
    "volgorde. Antwoord in EXACT dit formaat, vier regels:\n"
    "WORKERS: <komma-gescheiden uit: antwoord, annotatie, werkgebied, deelvragen, begrippen>\n"
    "SPECIALIST: <definitie|duiding|algemeen>\n"
    "TAAK: <alleen bij deelvragen, begrippen, het dossier aanvullen of het werkgebied (of zijn deelvragen) "
    "annoteren: één taak uit de lijsten hieronder; anders leeg>\n"
    "PLAN: <1-2 zinnen aanpak, of AFWIJZEN als de vraag niet over Nederlandse wet- en regelgeving "
    "gaat>\n"
    "AFWIJZEN is alleen voor vragen die BUITEN de wetgeving vallen: het weer, actualiteit, "
    "programmeren, rekensommen, meningen. Een vraag over een werkgebied, zijn deelvragen, bronnen, "
    "begrippen of annotaties gaat over wetgeving en wijs je nooit af. Gaat de vraag wél over een wet, "
    "een bepaling of een juridisch begrip, dan kies je 'antwoord' – óók als je de genoemde regeling niet kent of denkt "
    "dat ze niet in de graaf zit. Dat is niet aan jou om te weten: je hebt geen tools en je hebt niet "
    "gekeken. De worker zoekt het op en zegt zelf dat het niet in de kennisgraaf staat als hij niets "
    "vindt – en vindt hij iets aangrenzends, dan is dat een beter antwoord dan een afwijzing.\n"
    "Kies 'annotatie' als de gebruiker vraagt een ARTIKEL of LID te ANNOTEREN volgens het JAS (de "
    "juridische elementen markeren en classificeren). Kies anders 'antwoord' (een vraag beantwoorden, "
    "duiden of een begrip definiëren) met de passende SPECIALIST: 'definitie' voor begrip-/definitie"
    "vragen, 'duiding' voor betekenis/structuur/samenhang van een bepaling, anders 'algemeen'. "
    "SPECIALIST geldt alleen voor 'antwoord'. Kies 'werkgebied' (alleen) als de gebruiker een "
    "werkgebied wil samenstellen of een wetsanalyse wil beginnen, of als het bericht een antwoord is "
    "op een open vraag van het samenstellen of aanvullen (zie OPEN KAARTJE). Kies 'werkgebied' met TAAK: "
    "aanvullen als de gebruiker in een bestaand werkgebied een gegeven van het dossier wil invullen of "
    "wijzigen (naam, aanleiding, context, doel, analysevraag, praktijkvoorbeeld, afbakening) – deelvragen en "
    "bronnen horen bij 'deelvragen'.\n"
    "Kies 'deelvragen' (alleen) als de gebruiker in een werkgebied iets met de deelvragen of de bronnen wil "
    "laten DOEN. TAAK: voorstellen (deelvragen opstellen bij de analysevraag), verbeteren (één deelvraag "
    "scherper formuleren of splitsen), bronnen_zoeken (bepalingen zoeken die bij het werkgebied of een "
    "deelvraag horen, of wat er nog ontbreekt), dekking (is een deelvraag, of zijn de deelvragen, gedekt).\n"
    "Kies 'begrippen' (alleen) als de gebruiker in een werkgebied iets met de begrippen wil laten DOEN. TAAK: "
    "voorstellen (begrippen voorstellen uit de annotaties), meedenken (meedenken over twijfelpunten en "
    "definities), brondefinitie (de definitie van een vastgelegd begrip in de wet zoeken), scherper (een "
    "scherpere definitie), uitleg (de uitleg bij een vastgelegd begrip schrijven, in eenvoudige taal of B1), "
    "voorbeelden (voorbeelden bij een begrip), betekenisverschil (het verschil tussen "
    "twee begrippen), uitwerken (een begrip volledig uitwerken), relaties (de relaties van een begrip).\n"
    "Kies 'annotatie' met TAAK: werkgebied als de gebruiker het hele werkgebied wil laten annoteren ('annoteer "
    "wat nog niet geannoteerd is'), en met TAAK: deelvragen als hij alleen de bepalingen onder de deelvragen wil "
    "laten annoteren, of onder één deelvraag ('annoteer de bronnen van de deelvragen', 'annoteer deelvraag 2'); "
    "één artikel of lid annoteren is 'annotatie' zonder taak.\n"
    "Een vraag om UITLEG over een deelvraag, bron of begrip ('waarom hoort artikel 9 bij deelvraag 2?', 'wat "
    "betekent dit begrip?') is 'antwoord' met SPECIALIST duiding. De wettelijke definitie van een term, zonder "
    "dat het om een vastgelegd begrip van een werkgebied gaat, is 'antwoord' met SPECIALIST definitie. 'Welke "
    "artikelen gaan over X?' is 'antwoord'. Heeft de analist een object aangewezen in de werkplek, dan gaat de "
    "vraag daar meestal over: bij een deelvraag of bron ligt 'deelvragen' voor de hand, bij een begrip 'begrippen' – "
    "maar alleen als er om een van hun taken gevraagd wordt. Past geen van de taken, kies dan geen agent en laat "
    "TAAK leeg."
)

# Alleen als er een samenstelling (of een aanvulling) loopt: het kaartje dat open staat. Een getypt antwoord in het
# invoerveld ("Box 3", "geen overgangsrecht") is dan een antwoord op dat kaartje, geen nieuwe vraag.
INTAKE_SYSTEM = (
    "\n\nOPEN KAARTJE: Lex {wat} en vroeg zojuist: \"{vraag}\". "
    "Is het bericht een antwoord op die vraag (een naam, een aanleiding, context of doel, een vraag, een "
    "praktijkvoorbeeld, deelvragen, wat erbuiten valt, een regeling), "
    "kies dan WORKERS: werkgebied, zonder TAAK. Is het een andere vraag over wetgeving, kies dan zoals altijd; het "
    "kaartje blijft open staan."
)

# Alleen met een gesprek ervóór: dan moet de supervisor eerst weten waar een korte vervolgvraag
# ("waarom?", "en lid 2?", "doe hetzelfde voor artikel 10") over gaat, vóór hij kiest. Zonder dit
# blok routeerde hij de kale tekst – "waarom?" werd een afwijzing of een plan zonder onderwerp.
VERVOLG_SYSTEM = (
    "\n\nDIT IS EEN VERVOLGVRAAG in een lopend gesprek. Het gesprek tot nu toe en de GESPREKSCONTEXT "
    "staan hieronder. Zet als EERSTE regel:\n"
    "VRAAG: <de vraag zó herschreven dat hij zonder het gesprek te begrijpen is: vervang 'dat', "
    "'die markering', 'dit artikel', 'lid 2', 'hetzelfde' door wat er bedoeld wordt – regeling, "
    "artikel, lid, de markering met klasse en tekst. Verander niets aan wat er gevraagd wordt.>\n"
    "Kies daarna WORKERS/SPECIALIST/PLAN voor die herschreven vraag. Een vraag óver een markering die al "
    "gemaakt is (waarom deze klasse, leg uit, klopt dit, had het iets anders kunnen zijn) is 'antwoord' "
    "met SPECIALIST duiding – niet 'annotatie'. Alleen een vraag om (opnieuw of verder) te annoteren of "
    "te markeren, ook als 'doe hetzelfde voor lid 2', is 'annotatie'. Een vervolgvraag in een gesprek "
    "over wetgeving wijs je niet af omdat hij op zichzelf kort of vaag is; een vervolg op werk aan een "
    "werkgebied (deelvragen, bronnen, begrippen, meedenken) ook niet."
)

_QA_SPECIALISTS = ("definitie", "duiding", "algemeen")

# De workers die bestaan. Alles daarbuiten is een verzinsel van het model en telt niet
# mee: werd élke onbekende naam stilzwijgend een extra ANTWOORD-worker, dan beantwoordde "WORKERS:
# antwoord, samenvatten" dezelfde vraag twee keer – dubbele kosten, twee antwoorden.
_WORKERS = ("antwoord", "annotatie", "werkgebied", "deelvragen", "begrippen")
# Workers die met niets ketenen: een eigen gesprek van kaartjes, of één taak van een agent.
_ALLEEN = ("werkgebied", "deelvragen", "begrippen")

# Meer dan twee schakels heeft geen enkele vraag nodig (annoteren en dan samenvatten is de langste
# zinnige keten). Zonder plafond kan één supervisor-respons de beurt willekeurig lang maken.
_MAX_WORKERS = 2


def parse_vraag(text: str) -> str:
    """De zelfstandig geformuleerde vraag uit een `VRAAG:`-regel; leeg als die er niet is."""
    for line in text.splitlines():
        if line.strip().upper().startswith("VRAAG:"):
            return line.strip().split(":", 1)[1].strip()
    return ""


def parse_taak(text: str) -> str:
    """De taak uit een `TAAK:`-regel, in kleine letters; leeg als die er niet is. Of de taak bij de agent
    hoort, toetst de aanroeper (`agents.register.is_taak`)."""
    for line in text.splitlines():
        if line.strip().upper().startswith("TAAK:"):
            return line.strip().split(":", 1)[1].strip().strip(".`'\"").lower()
    return ""


def parse_supervisor(text: str) -> tuple[list[str], str, bool]:
    """(worker_plan, plan, afwijzen).

    `worker_plan` is een geordende lijst specialist-namen die de agent-node draait: een
    `antwoord`-worker wordt de gekozen QA-specialist, een `annotatie`-worker wordt 'annotatie'.

    `afwijzen` betekent dat de supervisor de vraag buiten de scope plaatste. Dat stond al in het
    promptformaat maar werd nergens gelezen: het woord "AFWIJZEN" ging als plan de systeemprompt van
    de specialist in, waarna een tweede modelbeslissing bepaalde wat er gebeurde. Nu is het een
    besluit dat de orkestrator uitvoert – de vraag eindigt vóór de eerste tool-call.
    """
    workers_raw, qa_specialist, plan = "", "algemeen", ""
    for line in text.splitlines():
        low = line.strip()
        up = low.upper()
        if up.startswith("WORKERS:"):
            workers_raw = low.split(":", 1)[1].strip().lower()
        elif up.startswith("SPECIALIST:"):
            val = low.split(":", 1)[1].strip().lower()
            if val in _QA_SPECIALISTS:
                qa_specialist = val
        elif up.startswith("PLAN:"):
            plan = low.split(":", 1)[1].strip()
    if not plan:
        plan = text.strip()

    # Alleen bekende workers, en nooit meer dan het plafond. Blijft er niets over, dan is
    # 'antwoord' de veilige terugval – een beurt zonder worker zou niets doen.
    workers = [w.strip() for w in workers_raw.split(",") if w.strip() in _WORKERS][:_MAX_WORKERS]
    for alleen in _ALLEEN:
        if alleen in workers:
            # Samenstellen is een eigen gesprek van vragen en kaartjes, en een agent doet één taak: ze
            # ketenen met niets.
            return [alleen], plan, False
    plan_spec = ["annotatie" if w == "annotatie" else qa_specialist for w in workers or ["antwoord"]]
    return plan_spec, plan, plan.strip().upper().startswith("AFWIJZEN")
