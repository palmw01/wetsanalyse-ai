import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Markdown } from "./Markdown";

const html = (tekst: string) => renderToStaticMarkup(createElement(Markdown, { tekst }));
const waarden = (uit: string) => [...uit.matchAll(/<li[^>]*?value="(\d+)"/g)].map((m) => Number(m[1]));

// De getallen in een antwoord zijn inhoud: "3." in een opsomming uit de wet is onderdeel 3. De markdown-laag
// nummert anders zelf: de browser begint weer bij 1, en dat verspringt zodra de stroom is afgelopen.
describe("Markdown laat lijstnummers staan", () => {
  it("een lijst die bij 3 begint", () => {
    expect(waarden(html("3. drie\n4. vier"))).toEqual([3, 4]);
  });
  it("een lijst met een gat", () => {
    expect(waarden(html("1. een\n3. drie"))).toEqual([1, 3]);
  });
  it("een lijst die na een alinea verdergaat", () => {
    expect(waarden(html("1. een\n\nTussenzin.\n\n2. twee"))).toEqual([1, 2]);
  });
  it("een geneste lijst", () => {
    expect(waarden(html("2. buiten\n\n   5. binnen\n   7. binnen"))).toEqual([2, 5, 7]);
  });
  it("een lijst in een quote, en de haakjesvorm", () => {
    expect(waarden(html("> 4. in een quote"))).toEqual([4]);
    expect(waarden(html("2) haakje"))).toEqual([2]);
  });
  it("een opsomming krijgt geen nummer, ook niet als het item met een getal begint", () => {
    expect(waarden(html("- 3 dagen\n- los"))).toEqual([]);
  });
});

describe("Markdown wijst een citatie zo diep aan als de tekst", () => {
  it("de chip noemt het onderdeel, ook als de bron het artikel is", () => {
    const uri = "urn:bwb:BWBR0004770:artikel:2";
    const uit = renderToStaticMarkup(createElement(Markdown, { tekst: "Zie artikel 2, eerste lid, onderdeel m.", bronnen: [{ label: "Artikel 2", uri }] }));
    expect(uit).toContain('title="Bron: Artikel 2, lid 1, onderdeel m"');
    expect(uit.replace(/<[^>]+>/g, "")).toContain("Zie artikel 2, eerste lid, onderdeel m.");
  });
});

// Modeltekst is de standaard: een link gaat alleen naar de bron. Alleen wat een mens schreef kiest `vrij`.
describe("Markdown en links", () => {
  const vrij = (tekst: string) => renderToStaticMarkup(createElement(Markdown, { tekst, links: "vrij" }));
  it("laat een link naar de wet door", () => {
    expect(html("[art. 9](https://wetten.overheid.nl/BWBR0004770/#Artikel9)")).toContain('href="https://wetten.overheid.nl/');
  });
  it("maakt van een vreemde host platte tekst", () => {
    const uit = html("[klik](https://voorbeeld.test/?q=vraag)");
    expect(uit).not.toContain("href");
    expect(uit).toContain("klik");
  });
  it("laat een beheerbericht elke http(s)-link, maar geen ander schema", () => {
    expect(vrij("[klik](https://voorbeeld.test/)")).toContain('href="https://voorbeeld.test/"');
    expect(vrij("[klik](mailto:a@b.nl)")).not.toContain("href");
  });
});
