"""Rolselectie uit het gebundelde pakket, zonder skill/PDF/runtime-I/O."""
import hashlib
import logging

from .methodepakket import PAKKET

logger = logging.getLogger('graph_qa.methode')


def instructies(rol: str) -> str:
    ids = PAKKET['rollen'][rol]  # Onbekende interne rol faalt expliciet.
    logger.info('Wetsanalysemethode geladen', extra={
        'categorie': 'technisch', 'methode_rol': rol,
        'methode_versie': PAKKET['versie'], 'methode_sha256': PAKKET['sha256'],
        'methode_secties': ids,
    })
    return '\n\n'.join([
        f"WETSANALYSE {PAKKET['versie']} — rol {rol}",
        *(f"[{key}]\n{PAKKET['secties'][key]['tekst']}" for key in ids),
    ])


def vingerafdruk(rol: str) -> str:
    """De methodetekst van een rol als vingerafdruk: twaalf hextekens over de sha256 van haar secties uit `PAKKET`.

    Eén bron voor wie wil weten welke methode een rol droeg: de logregel `model_aanroep` (naast `system_hash`, de
    vingerafdruk van de hele stabiele prompt zoals hij verstuurd is) en de catalogus (ADR-014). Verandert `system_hash`
    terwijl deze gelijk blijft, dan kwam de wijziging uit de code en niet uit de skill. Onbekende rol: leeg."""
    ids = PAKKET['rollen'].get(rol)
    if not ids:
        return ''
    reeks = '\n'.join(f"{key}:{PAKKET['secties'][key]['sha256']}" for key in ids)
    return hashlib.sha256(reeks.encode('utf-8')).hexdigest()[:12]
