import assert from "node:assert/strict";
import { test } from "node:test";
import { BronClient, kiesToestand, tekstVan, toestandenUitSru, zoekArtikel } from "./bron.js";

const record = (vanaf: string, tot: string) =>
  `<recordData><gzd xmlns="x"><dcterms:title>Wet</dcterms:title>
   <overheidbwb:geldigheidsperiode_startdatum>${vanaf}</overheidbwb:geldigheidsperiode_startdatum>
   <overheidbwb:geldigheidsperiode_einddatum>${tot}</overheidbwb:geldigheidsperiode_einddatum>
   <overheidbwb:locatie_toestand>https://repository.officiele-overheidspublicaties.nl/bwb/BWBR0000001/${vanaf}_0/xml/t.xml</overheidbwb:locatie_toestand>
   </gzd></recordData>`;
const SRU = `<searchRetrieveResponse>${record("2026-01-01", "2026-06-30")}${record("2024-01-01", "2025-12-31")}</searchRetrieveResponse>`;

// De vorm van een echte toestand, met een tekst na de opsomming en een verwijzing in de lopende tekst.
const TOESTAND = `<?xml version="1.0"?><toestand><wetgeving>
<artikel bwb-ng-variabel-deel="/H1/Artikel2" label="Artikel 2"><kop><label>Artikel</label><nr status="officieel">2</nr></kop>
  <lid bwb-ng-variabel-deel="/H1/Artikel2/Lid1"><lidnr status="officieel">1.</lidnr>
    <al>Dit lid noemt <intref doc="x&amp;y">artikel 1</intref> &amp; meer:</al>
    <lijst><li><li.nr>a.</li.nr><al>eerste;</al><al>tweede alinea van a;</al></li><li><li.nr>b.</li.nr><al>laatste.</al></li></lijst>
    <al>Slottekst.</al>
    <meta-data><jcis><jci verwijzing="jci1.3:c:BWBR0000001&amp;artikel=2&amp;lid=1"/></jcis></meta-data></lid>
  <lid bwb-ng-variabel-deel="/H1/Artikel2/Lid10"><lidnr status="officieel">10</lidnr><al>Tiende.</al></lid>
</artikel>
<artikel bwb-ng-variabel-deel="/H1/Artikel3"><kop><nr>3:40</nr></kop><al>Geen leden.</al>
  <wijzig><artikel bwb-ng-variabel-deel="/citaat"><kop><nr>2</nr></kop><al>Geciteerd.</al></artikel></wijzig>
</artikel>
<bijlage><artikel bwb-ng-variabel-deel="/Bijlage/Artikel2"><kop><nr>2</nr></kop><al>In de bijlage.</al></artikel></bijlage>
</wetgeving></toestand>`;

test("toestanden: oudste eerst, zonder peildatum de nieuwste, met peildatum de geldige", () => {
  const lijst = toestandenUitSru(SRU);
  assert.deepEqual(lijst.map((t) => t.geldig_vanaf), ["2024-01-01", "2026-01-01"]);
  assert.equal(lijst[0].titel, "Wet");
  assert.equal(kiesToestand(lijst).geldig_vanaf, "2026-01-01");
  assert.equal(kiesToestand(lijst, "2025-06-01").geldig_vanaf, "2024-01-01");
  assert.throws(() => kiesToestand(lijst, "2020-01-01"), /Geen toestand/);
});

test("een artikel: alleen het hoogste niveau, en elk artikel met dat nummer", () => {
  const treffers = zoekArtikel(TOESTAND, "artikel 2");
  assert.deepEqual(treffers.map((t) => t.plaats), ["/H1/Artikel2", "/Bijlage/Artikel2"]);
  assert.match(zoekArtikel(TOESTAND, "3:40")[0].xml, /Geciteerd/);
  assert.throws(() => zoekArtikel(TOESTAND, "99"), /niet in deze toestand/);
});

test("een lid: nummer met of zonder punt, en niet het lid dat ermee begint", () => {
  const [lid1] = zoekArtikel(TOESTAND, "2", "1");
  assert.equal(lid1.plaats, "/H1/Artikel2/Lid1");
  assert.match(lid1.xml, /^<lid /);
  assert.match(lid1.xml, /jci1\.3/);
  assert.throws(() => zoekArtikel(TOESTAND, "3:40", "1"), /geen lid 1/);
});

test("de tekst volgt de XML: slottekst na de opsomming, tweede alinea binnen het onderdeel", () => {
  assert.equal(
    tekstVan(zoekArtikel(TOESTAND, "2", "1")[0].xml),
    "1. Dit lid noemt artikel 1 & meer:\na. eerste;\ntweede alinea van a;\nb. laatste.\nSlottekst.",
  );
});

test("lees: 406 van de SRU-dienst is geen fout, en een herhaling haalt niets opnieuw op", async () => {
  const urls: string[] = [];
  const nep = (async (url: string | URL, init?: RequestInit) => {
    urls.push(String(url));
    assert.equal(init?.redirect, "error");
    assert.match((init?.headers as Record<string, string>)["User-Agent"], /^wetsanalyse-acceptatie-mcp/);
    return String(url).includes("/sru/") ? new Response(SRU, { status: 406 }) : new Response(TOESTAND);
  }) as typeof fetch;
  const client = new BronClient(nep);
  const uit = await client.lees({ bwb_id: "BWBR0000001", artikel: "2", lid: "10" });
  assert.equal(uit.toestand.geldig_vanaf, "2026-01-01");
  assert.equal(uit.aantal_toestanden, 2);
  assert.equal(uit.treffers[0].tekst, "10 Tiende.");
  await client.lees({ bwb_id: "BWBR0000001", artikel: "3:40" });
  assert.equal(urls.length, 2);
});

test("een botcontrole of foutpagina is een melding, zonder tweede poging", async () => {
  let keer = 0;
  const nep = (async () => {
    keer += 1;
    return new Response("<html>Controleer dat u geen robot bent</html>", { status: 403, headers: { "content-type": "text/html" } });
  }) as typeof fetch;
  await assert.rejects(new BronClient(nep).lees({ bwb_id: "BWBR0000001", artikel: "2" }), /HTTP 403.*bevinding/);
  assert.equal(keer, 1);
});

test("een locatie buiten de repository wordt niet opgehaald", async () => {
  const urls: string[] = [];
  const sru = SRU.replaceAll("https://repository.officiele-overheidspublicaties.nl", "https://elders.example.org");
  const nep = (async (url: string | URL) => {
    urls.push(String(url));
    return new Response(sru);
  }) as typeof fetch;
  await assert.rejects(new BronClient(nep).lees({ bwb_id: "BWBR0000001", artikel: "2" }), /Onverwachte bronlocatie/);
  assert.equal(urls.length, 1);
});

test("ongeldige invoer komt niet in een url", async () => {
  const nep = (async () => assert.fail("geen aanroep verwacht")) as typeof fetch;
  await assert.rejects(new BronClient(nep).lees({ bwb_id: "x&query=y", artikel: "2" }), /bwb_id/);
  await assert.rejects(new BronClient(nep).lees({ bwb_id: "BWBR0000001", artikel: "2", peildatum: "gisteren" }), /peildatum/);
});
