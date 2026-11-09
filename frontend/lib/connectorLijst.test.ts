import { describe, expect, it } from "vitest";
import { maakConnectorLijst } from "./connectorLijst";

const KST = { naam: "kamerstukken", label: "Kamerstukken", brontype: "kamerstuk", beschikbaarheid: "aan" as const };

describe("connectorLijst", () => {
  it("houdt de laatst bekende lijst over een nieuwe mount heen", async () => {
    const lijst = maakConnectorLijst();
    expect(lijst.lees()).toEqual({ beschikbaar: [], laden: null });
    await lijst.ververs(async () => ({ connectors: [KST] }));
    // Een volgende mount leest dezelfde lijst meteen, nog voor zijn eigen verzoek antwoordt.
    expect(lijst.lees()).toEqual({ beschikbaar: [KST], laden: "ok" });
  });

  it("een mislukte poging laat de lijst staan en zegt het", async () => {
    const lijst = maakConnectorLijst();
    await lijst.ververs(async () => ({ connectors: [KST] }));
    await lijst.ververs(async () => { throw new Error("504"); });
    expect(lijst.lees()).toEqual({ beschikbaar: [KST], laden: "mislukt" });
    await lijst.ververs(async () => ({ connectors: [KST] }));
    expect(lijst.lees().laden).toBe("ok");
  });

  it("mislukt zonder eerdere lijst: leeg, maar wel als mislukt", async () => {
    const lijst = maakConnectorLijst();
    await lijst.ververs(async () => { throw new Error("502"); });
    expect(lijst.lees()).toEqual({ beschikbaar: [], laden: "mislukt" });
  });

  it("één verzoek tegelijk, en luisteraars horen elke wijziging", async () => {
    const lijst = maakConnectorLijst();
    let n = 0, gehoord = 0;
    lijst.abonneer(() => { gehoord++; });
    const haal = async () => { n++; return { connectors: [KST] }; };
    await Promise.all([lijst.ververs(haal), lijst.ververs(haal)]);
    expect(n).toBe(1);
    expect(gehoord).toBe(1);
  });

  it("legt de bronstand van een beurt over de lijst, en meldt alleen een echte wijziging", async () => {
    const lijst = maakConnectorLijst();
    await lijst.ververs(async () => ({ connectors: [KST] }));
    let gehoord = 0;
    lijst.abonneer(() => { gehoord++; });
    lijst.legBronstandOver([{ naam: "kamerstukken", reden: "aan" }]);
    expect(gehoord).toBe(0);
    lijst.legBronstandOver([{ naam: "kamerstukken", reden: "register_onleesbaar" }]);
    expect(lijst.lees().beschikbaar[0].beschikbaarheid).toBe("onbekend");
    expect(gehoord).toBe(1);
  });
});
