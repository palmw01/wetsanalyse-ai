"""Live meting spoor M: kaart, scherper en voorbeelden op casus A en B. Draai vanuit tools/graph-qa van de
te meten versie: python meet.py <casus.json> <uit.json> <runs>. Werkt op de code van vóór en na spoor M."""
import hashlib, inspect, json, sys, time
from agent.config import Settings
from agent.adapters.anthropic_llm import AnthropicLLM
from agent.begrippen_pipeline import kaart as kaart_mod, kaartacties as ka, keten, definities, model as M

casus_pad, uit_pad, runs = sys.argv[1], sys.argv[2], int(sys.argv[3])
data = json.load(open(casus_pad))
nodes = {n["bron_iri"]: n for n in data["nodes"]}
NIEUW = hasattr(M, "Onderzoek")
DEF = {"A": "De wijziging van een voorlopige aanslag inkomstenbelasting of vennootschapsbelasting in een andere voorlopige aanslag.",
       "B": "De inkomstenbelasting of vennootschapsbelasting die met een aanslag wordt geheven."}
NAAM = {"A": "herziening", "B": "belasting"}
LEDEN = {"A": ("e0",), "B": ("e0", "e1")}

def bron(n, cls=M.Bron, **x):
    return cls(bron_iri=n["bron_iri"], tekst=n["tekst"], bron_hash=n["bron_hash"], label=n["label"], regeling="BWBR0002320", **x)

def opzet(c):
    fs = data["casus"][c]["formuleringen"]
    m = M.Manifest(bronnen=tuple(bron(nodes[i]) for i in sorted({f["bron_iri"] for f in fs})),
                   formuleringen=tuple(M.Formulering(element_id=f"e{i}", **f) for i, f in enumerate(fs)))
    if not NIEUW:
        return m, None
    art = fs[0]["bron_iri"].rsplit(":lid:", 1)[0]
    eigen = {b.bron_iri for b in m.bronnen}
    ctx = tuple(bron(n, M.Contextbron, rol=M.Rol.ONDERZOEK, reden=M.Reden.ZELFDE_ARTIKEL, voor=("e0",))
                for i, n in nodes.items() if i.startswith(art + ":") and n["tekst"] and i not in eigen)
    return m, M.Onderzoek(manifest_id=m.id, bronnen=ctx)

def kw(fn, **x):
    ps = inspect.signature(fn).parameters
    return {k: v for k, v in x.items() if k in ps}

s = Settings.from_env()
uit = {"nieuw": NIEUW, "model": s.llm_model, "runs": []}
for r in range(runs):
    for c in ("A", "B"):
        m, o = opzet(c)
        rij = {"run": r, "casus": c}
        taal = {t.element_id: t for t in keten.analyseer(m).taal}
        wts = definities.wettelijke_termen(m, taal)
        gid = "G" + hashlib.sha256(c.encode()).hexdigest()[:12]
        # kaart
        llm = AnthropicLLM(s); t0 = time.time()
        k, opd = kaart_mod.basis(m, taal, wts, gid, LEDEN[c], True, **kw(kaart_mod.basis, onderzoek=o))
        kaarten = kaart_mod.vul(llm, s.llm_model, m, [opd], {gid: True}) if opd else [k]
        kk = kaarten[0]
        rij["kaart"] = {"definitie": kk.definitie, "herkomst": kk.herkomst.value if kk.herkomst else None,
                        "fragmenten": [f.model_dump() for f in kk.fragmenten], "motivatie": kk.motivatie,
                        "aandachtspunten": list(kk.aandachtspunten), "naam": kk.naam,
                        "duiding": kk.duiding.model_dump() if getattr(kk, "duiding", None) else None,
                        "tokens": vars(llm.meter)["invoer"] + vars(llm.meter)["uitvoer"], "s": round(time.time() - t0, 1)}
        # scherper
        kant = ka.Kant(id="b", inhoud={"naam": NAAM[c]}, leden=LEDEN[c])
        llm = AnthropicLLM(s); t0 = time.time()
        u = ka.scherper(llm, s.llm_model, m, kant, {}, **kw(ka.scherper, onderzoek=o))
        rij["scherper"] = {"voorstellen": u.voorstellen, "melding": u.melding,
                           "tokens": vars(llm.meter)["invoer"] + vars(llm.meter)["uitvoer"], "s": round(time.time() - t0, 1)}
        # voorbeelden op een vaste definitie
        kant = ka.Kant(id="b", inhoud={"naam": NAAM[c], "definitie": DEF[c]}, leden=LEDEN[c])
        llm = AnthropicLLM(s); t0 = time.time()
        u = ka.voorbeelden(llm, s.llm_model, m, kant, {}, **kw(ka.voorbeelden, onderzoek=o))
        rij["voorbeelden"] = {"voorstellen": u.voorstellen, "melding": u.melding,
                              "tokens": vars(llm.meter)["invoer"] + vars(llm.meter)["uitvoer"], "s": round(time.time() - t0, 1)}
        uit["runs"].append(rij)
        print(c, r, "kaart", rij["kaart"]["herkomst"], "scherper", len(rij["scherper"]["voorstellen"]),
              "vb", len(rij["voorbeelden"]["voorstellen"]), flush=True)
json.dump(uit, open(uit_pad, "w"), ensure_ascii=False, indent=1)
