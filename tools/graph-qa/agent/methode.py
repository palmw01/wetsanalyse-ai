"""Rolselectie uit het gebundelde pakket, zonder skill/PDF/runtime-I/O."""
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
