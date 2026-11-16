import sys, glob
from pathlib import Path
from bronmodel.bwb.parser import ToestandParser
def alle(wet):
    uit = {}
    def loop(n):
        for attr in ("structuurdelen", "subdelen", "artikelen", "losse_artikelen", "leden", "onderdelen", "divisies", "bijlagen"):
            for k in getattr(n, attr, []) or []:
                for b in getattr(k, "definieert_begrippen", []) or []:
                    uit.setdefault(b, getattr(k, "id", "?"))
                loop(k)
    loop(wet); return uit
totaal = 0
for f in sorted(glob.glob(sys.argv[1] + "/*/*_0.xml")):
    oud, nieuw = alle(ToestandParser().parse(Path(f))), alle(ToestandParser(aanduiding=True).parse(Path(f)))
    erbij = {b: i for b, i in nieuw.items() if b not in oud}
    totaal += len(erbij)
    print(f"{Path(f).name[:11]}: {len(oud)} -> {len(nieuw)} (+{len(erbij)})")
    for b, i in erbij.items(): print("     ", repr(b), "|", i[-60:])
print("totaal erbij", totaal)
