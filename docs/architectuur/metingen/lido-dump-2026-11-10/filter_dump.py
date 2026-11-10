"""Filter de LiDO-dump streamend op een paar BWB-id's: één doorgang, nooit uitgepakt op schijf of in het geheugen.

Leest N-Triples van stdin (`zcat lido-export.nt.gz | python -I filter_dump.py <uitmap> BWBR… …`) en schrijft per BWB-id
de regels waarin dat id voorkomt (als onderwerp, object of in een literal) naar `<uitmap>/<BWB>.nt.gz`. Daarnaast een
telling van alle predicaten over de hele dump (`predicaten.json`) en de duur, het piekgeheugen en het aantal regels
(`filter-stat.json`).
"""
from __future__ import annotations

import collections
import gzip
import json
import pathlib
import resource
import sys
import time


def main() -> None:
    uitmap = pathlib.Path(sys.argv[1])
    ids = [i.encode() for i in sys.argv[2:]]
    uitmap.mkdir(parents=True, exist_ok=True)
    uit = {i: gzip.open(uitmap / f"{i.decode()}.nt.gz", "wb", compresslevel=6) for i in ids}
    per_id = collections.Counter()
    pred = collections.Counter()
    t0 = time.monotonic()
    regels = 0
    bytes_ = 0
    for regel in sys.stdin.buffer:
        regels += 1
        bytes_ += len(regel)
        # het predicaat: tweede term, altijd een IRI in N-Triples
        p1 = regel.find(b"> <")
        if p1 > 0:
            p2 = regel.find(b">", p1 + 3)
            pred[regel[p1 + 2:p2 + 1]] += 1
        if b"BWBR00" in regel:  # snelle voortoets, alle drie de id's beginnen zo
            for i in ids:
                if i in regel:
                    uit[i].write(regel)
                    per_id[i.decode()] += 1
        if regels % 50_000_000 == 0:
            print(f"{regels:,} regels, {bytes_ / 1e9:.1f} GB, {time.monotonic() - t0:.0f} s", file=sys.stderr, flush=True)
    for f in uit.values():
        f.close()
    stat = {
        "regels": regels,
        "bytes_uitgepakt": bytes_,
        "seconden": round(time.monotonic() - t0, 1),
        "piek_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        "regels_per_id": dict(per_id),
        "bytes_gefilterd": {i.decode(): (uitmap / f"{i.decode()}.nt.gz").stat().st_size for i in ids},
    }
    (uitmap / "filter-stat.json").write_text(json.dumps(stat, indent=2))
    (uitmap / "predicaten.json").write_text(json.dumps(
        {k.decode(errors="replace"): v for k, v in pred.most_common()}, indent=1))
    print(json.dumps(stat))


if __name__ == "__main__":
    main()
