import { describe, expect, it } from "vitest";

import {
  VAKJES, adviezen, beginKoud, beginTekst, beurtenUitBerichten, boomVerbruik, contextRegel, grootste, grootsteRest,
  hoofdagent, kindRijen, kort, legenda, lijn, metBeurt, parseContextopbouw, procent, profielTekst, raster, rolLabel, signaal,
  totaalVerbruik, verloop, type Contextopbouw,
} from "./contextweergave";

/** De contextopbouw van een echte beurt op acceptatie (12 nov 2026): een koud begin, drie rondes van de antwoordlus. */
function opbouw(wijzig: (c: Record<string, any>) => void = () => {}): Contextopbouw {
  const ruw = {
    versie: 1, run_id: "r1", ouder_run_id: "", profiel_id: "", profiel_versie: "",
    agenten: [{
      rol: "antwoord", model: "claude-sonnet-4-6", venster: 1_000_000, historiegrens: 13806,
      venster_beurten: { in_venster: 1, gekrompen: 0, weggevallen: 0 },
      begin: { totaal: 27867, cache: { lees: 0, schrijf: 27864, nieuw: 3 }, tools_hash: "758623c1266b", system_hash: "5cc1b4215950" },
      laatste: {
        totaal: 30890, voorvoegsel: { omvang: 25009, exact: true }, cache: { lees: 30148, schrijf: 741, nieuw: 1 },
        delen: [
          { categorie: "systeem", omvang: 3300 }, { categorie: "methode", omvang: 1081 }, { categorie: "graaftools", omvang: 8284 },
          { categorie: "connectortools", omvang: 9363 }, { categorie: "sjablonen", omvang: 2981 },
          { categorie: "beurtcontext", omvang: 2830 }, { categorie: "beurt", omvang: 200 }, { categorie: "toolresultaten", omvang: 2851 },
        ],
      },
    }],
    verbruik: [
      { rol: "supervisor", model: "m", aanroepen: 1, invoer: 34, cache_lees: 2189, cache_schrijf: 0, uitvoer: 68, duur: 2747 },
      { rol: "antwoord", model: "m", aanroepen: 3, invoer: 5, cache_lees: 58012, cache_schrijf: 30889, uitvoer: 1815, duur: 33908 },
    ],
    som: { invoer: 39, cache_lees: 60201, cache_schrijf: 30889, uitvoer: 1883 },
    aanroepen: [{ rol: "supervisor", totaal: 2223, cache_lees: 2189, cache_schrijf: 0, invoer: 34, uitvoer: 68, ms: 2747, tools_hash: "", system_hash: "a22e" }],
  };
  wijzig(ruw);
  return parseContextopbouw(ruw)!;
}

describe("lezen", () => {
  it("leest de contextopbouw van graph-qa en laat onbekende velden vallen", () => {
    const c = opbouw((r) => { r.nieuw_veld = 1; });
    expect(c.agenten[0].laatste.totaal).toBe(30890);
    expect(c.agenten[0].laatste.voorvoegsel).toEqual({ omvang: 25009, exact: true });
    expect(c.verbruik.map((v) => v.rol)).toEqual(["supervisor", "antwoord"]);
    expect("nieuw_veld" in c).toBe(false);
  });

  it("leest het profiel per agent, en een agent zonder profiel heeft er geen", () => {
    expect(profielTekst(hoofdagent(opbouw())!)).toBe("");
    const met = hoofdagent(opbouw((r) => { r.agenten[0].profiel_id = "bronnenzoeker"; r.agenten[0].profiel_versie = "3"; }))!;
    expect([met.profiel_id, met.profiel_versie]).toEqual(["bronnenzoeker", "3"]);
    expect(profielTekst(met)).toBe("bronnenzoeker, versie 3");
    expect(profielTekst({ profiel_id: "bronnenzoeker", profiel_versie: "" })).toBe("bronnenzoeker");
  });

  it("een vorm die niet past is geen meting, nooit een fout", () => {
    for (const v of [null, undefined, "x", [], {}, { versie: "1" }, { agenten: [] }]) expect(parseContextopbouw(v)).toBeUndefined();
    const half = parseContextopbouw({ versie: 1, agenten: [{ rol: "antwoord" }, "x"], verbruik: "nee" })!;
    expect(half.agenten).toEqual([]);
    expect(half.verbruik).toEqual([]);
    expect(half.som).toEqual({ invoer: 0, cache_lees: 0, cache_schrijf: 0, uitvoer: 0 });
  });

  it("haalt de beurten met een meting uit de berichten, in volgorde", () => {
    const c = opbouw();
    const beurten = beurtenUitBerichten([
      { rol: "user", run_id: "", contextopbouw: c },                      // een vraag draagt geen meting
      { rol: "assistant", run_id: "oud", contextopbouw: null },           // van vóór de meting
      { rol: "assistant", run_id: "r1", contextopbouw: c },
    ] as never);
    expect(beurten.map((b) => b.run_id)).toEqual(["r1"]);
  });

  it("een nieuwe meting vervangt die van dezelfde run en komt anders achteraan", () => {
    const een = opbouw(), twee = opbouw((r) => { r.run_id = "r2"; });
    const lijst = metBeurt(metBeurt([], een), twee);
    expect(lijst.map((b) => b.run_id)).toEqual(["r1", "r2"]);
    const opnieuw = metBeurt(lijst, opbouw((r) => { r.som.uitvoer = 5; }));
    expect(opnieuw.map((b) => b.run_id)).toEqual(["r1", "r2"]);
    expect(opnieuw[0].contextopbouw.som.uitvoer).toBe(5);
  });
});

describe("getallen in woorden", () => {
  it("kort af met de Nederlandse komma", () => {
    expect([980, 1234, 9950, 30890, 131_000, 1_000_000, 1_250_000].map(kort)).toEqual(["980", "1,2k", "10k", "31k", "131k", "1M", "1,3M"]);
  });

  it("noemt een aandeel nooit 0% als er iets is", () => {
    expect(procent(30890, 1_000_000)).toBe("3,1%");
    expect(procent(250, 1000)).toBe("25%");
    expect(procent(1, 1_000_000)).toBe("< 0,1%");
    expect(procent(0, 100)).toBe("0%");
    expect(procent(5, 0)).toBe("0%");
  });

  it("de regel van de meter is de omvang en het deel van het venster", () => {
    expect(contextRegel(hoofdagent(opbouw())!)).toBe("31k · 3,1%");
    expect(contextRegel(hoofdagent(opbouw((r) => { r.agenten[0].venster = 0; }))!)).toBe("31k");
  });

  it("het verbruik van de beurt is iets anders dan de context", () => {
    const c = opbouw();
    expect(totaalVerbruik(c.som)).toBe(93012);
    expect(hoofdagent(c)!.laatste.totaal).toBe(30890);
  });
});

describe("het raster en de legenda", () => {
  it("verdeelt precies, en bij gelijke rest in volgorde", () => {
    expect(grootsteRest([1, 1, 1], 10)).toEqual([4, 3, 3]);
    expect(grootsteRest([0, 0], 10)).toEqual([0, 0]);
    expect(grootsteRest([5, 13, 2, 977], 100).reduce((a, b) => a + b, 0)).toBe(100);
  });

  it("het raster is 100% van het verzoek, in de volgorde van het register", () => {
    const vakjes = raster(hoofdagent(opbouw())!);
    expect(vakjes).toHaveLength(VAKJES);
    const ids = vakjes.map((d) => d.id);
    expect([...new Set(ids)]).toEqual(["systeem", "methode", "graaftools", "connectortools", "sjablonen", "beurtcontext", "beurt", "toolresultaten"]);
    expect(ids.filter((i) => i === "connectortools")).toHaveLength(30);
  });

  it("de legenda noemt elke categorie met haar omvang, ook een die geen vakje krijgt", () => {
    const a = hoofdagent(opbouw((r) => { r.agenten[0].laatste.delen.push({ categorie: "historie", omvang: 12 }); }))!;
    const regels = legenda(a);
    expect(regels.map((r) => r.deel.id)).toContain("historie");
    expect(regels.find((r) => r.deel.id === "historie")).toMatchObject({ omvang: 12, aandeel: "< 0,1%", grens: 13806, geschat: true });
    expect(regels.find((r) => r.deel.id === "systeem")?.grens).toBeUndefined();
    expect(raster(a).some((d) => d.id === "historie")).toBe(false);
  });

  it("een onbekende categorie telt bij Overig, zodat de som klopt", () => {
    const a = hoofdagent(opbouw((r) => { r.agenten[0].laatste.delen.push({ categorie: "nieuw", omvang: 500 }, { categorie: "overig", omvang: 100 }); }))!;
    expect(legenda(a).find((r) => r.deel.id === "overig")?.omvang).toBe(600);
    expect(legenda(a).reduce((n, r) => n + r.omvang, 0)).toBe(30890 + 600);
  });

  it("de drie grootste delen staan in de tooltip van de meter", () => {
    expect(grootste(hoofdagent(opbouw())!).map((r) => r.deel.id)).toEqual(["connectortools", "graaftools", "systeem"]);
  });
});

describe("de adviezen en het signaal", () => {
  const warm = (r: Record<string, any>) => { r.agenten[0].begin.cache = { lees: 27000, schrijf: 800, nieuw: 3 }; };
  const ids = (c: Contextopbouw, vorige?: Contextopbouw) => adviezen(c, vorige).map((a) => a.id);

  it("een warm begin zonder bijzonderheden geeft alleen het advies over de bronnen naast de wet", () => {
    const c = opbouw(warm);
    expect(beginKoud(hoofdagent(c)!)).toBe(false);
    expect(ids(c)).toEqual(["veel_connectortools"]);
    expect(signaal(c)).toBeUndefined();
    expect(beginTekst(hoofdagent(c)!)).toMatch(/^Deze beurt begon warm: 27k kwam uit de cache, 800 is nieuw geschreven\.$/);
  });

  it("een koud begin met dezelfde tools is een pauze, met andere tools een wissel van bronnen", () => {
    const c = opbouw();
    expect(beginKoud(hoofdagent(c)!)).toBe(true);
    expect(ids(c)).toContain("koud_pauze");
    expect(ids(c, opbouw())).toContain("koud_pauze");
    const andere = opbouw((r) => { r.agenten[0].begin.tools_hash = "anders"; });
    expect(ids(c, andere)).toContain("koud_toolset");
    expect(ids(c, andere)).not.toContain("koud_pauze");
    expect(signaal(c)?.id).toBe("koud_pauze");
    // De cache is van iedereen met hetzelfde vaste deel: de tekst wijst niet naar de jurist.
    expect(adviezen(c).find((a) => a.id === "koud_pauze")?.tekst).not.toMatch(/\bjij\b|\bje was\b/i);
    expect(beginTekst(hoofdagent(c)!)).toMatch(/^Deze beurt begon koud: het vaste deel \(28k\) is opnieuw geschreven/);
  });

  it("een ingekorte historie en weggevallen beurten geven het signaal", () => {
    const ingekort = opbouw((r) => { warm(r); r.agenten[0].venster_beurten.gekrompen = 2; });
    expect(signaal(ingekort)?.id).toBe("historie_ingekort");
    const bijnaVol = opbouw((r) => { warm(r); r.agenten[0].laatste.delen.push({ categorie: "historie", omvang: 12500 }); });
    expect(ids(bijnaVol)).toContain("historie_ingekort");
    const net = opbouw((r) => { warm(r); r.agenten[0].laatste.delen.push({ categorie: "historie", omvang: 12000 }); });
    expect(ids(net)).not.toContain("historie_ingekort");
    const weg = opbouw((r) => { warm(r); r.agenten[0].venster_beurten.weggevallen = 3; });
    expect(adviezen(weg).find((a) => a.id === "beurten_weggevallen")?.tekst).toMatch(/^3 eerdere beurten zitten niet meer/);
    const een = opbouw((r) => { warm(r); r.agenten[0].venster_beurten.weggevallen = 1; });
    expect(adviezen(een).find((a) => a.id === "beurten_weggevallen")?.tekst).toMatch(/^Eén eerdere beurt zit niet meer/);
  });

  it("meer wettools dan bronnen naast de wet geeft geen advies, en een vol venster wel een signaal", () => {
    const c = opbouw((r) => { warm(r); r.agenten[0].laatste.delen = [{ categorie: "graaftools", omvang: 9000 }, { categorie: "connectortools", omvang: 100 }]; });
    expect(ids(c)).toEqual([]);
    const vol = opbouw((r) => { warm(r); r.agenten[0].venster = 38_000; });
    expect(ids(vol)).toContain("venster_vol");
    expect(adviezen(vol).find((a) => a.id === "venster_vol")?.signaal).toBe(true);
  });

  it("een beurt zonder agent met een lus heeft geen adviezen", () => {
    expect(adviezen(opbouw((r) => { r.agenten = []; }))).toEqual([]);
  });
});

describe("het verloop en de boom", () => {
  it("geeft per beurt de context en het verbruik", () => {
    const beurten = metBeurt(metBeurt([], opbouw()), opbouw((r) => { r.run_id = "r2"; r.agenten = []; }));
    expect(verloop(beurten)).toEqual([{ run_id: "r1", context: 30890, verbruik: 93012 }, { run_id: "r2", context: 0, verbruik: 93012 }]);
  });

  it("tekent een lijntje binnen zijn vak", () => {
    expect(lijn([], 100, 40)).toBe("");
    expect(lijn([5], 100, 40)).toBe("0,0 100,0");
    expect(lijn([0, 50, 100], 100, 40)).toBe("0,40 50,20 100,0");
  });

  it("de boom noemt de kinderen van deze beurt, en zegt het als er een niet gemeten is", () => {
    const kind = (run: string, ouder: string) => ({ run_id: run, contextopbouw: opbouw((r) => { r.run_id = run; r.ouder_run_id = ouder; }) });
    const boom = { gesprek_id: "g", kinderen: [
      { gesprek_id: "k1", titel: "Deelvraag 1", berichten: [kind("a", "r1"), kind("b", "r1")] },
      { gesprek_id: "k2", titel: "Andere beurt", berichten: [kind("c", "r0")] },
      { gesprek_id: "k3", titel: "Loopt nog", berichten: [] },
    ] };
    const rijen = kindRijen(boom, "r1");
    expect(rijen.map((r) => [r.gesprek_id, r.gemeten, r.beurten.length])).toEqual([["k1", true, 2], ["k3", false, 0]]);
    expect(rijen[0].verbruik).toBe(2 * 93012);
    expect(rijen[0].context?.laatste.totaal).toBe(30890);
    expect(boomVerbruik(opbouw(), rijen)).toEqual({ totaal: 3 * 93012, volledig: false });
    expect(boomVerbruik(opbouw(), rijen.slice(0, 1)).volledig).toBe(true);
    // Bij een eerdere beurt staat een kind zonder meting er niet: het is aan geen beurt toe te wijzen.
    expect(kindRijen(boom, "r1", false).map((r) => r.gesprek_id)).toEqual(["k1"]);
    expect(kindRijen(boom, "r0", false).map((r) => r.gesprek_id)).toEqual(["k2"]);
    expect(kindRijen(undefined, "r1")).toEqual([]);
  });

  it("een rol heeft een naam in gewone taal, en een onbekende rol zijn eigen naam", () => {
    expect(rolLabel("supervisor")).toBe("Vraag indelen");
    expect(rolLabel("nieuw_ding")).toBe("nieuw_ding");
  });
});
