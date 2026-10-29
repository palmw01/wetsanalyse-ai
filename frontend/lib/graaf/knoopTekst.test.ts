import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { KnoopTekst } from "@/components/graaf/KnoopTekst";

it("toont het letterlijke streepje met een spatie vóór de brontekst", () => {
  const iri = "urn:bwb:BWBR0024096:id:Onderdeel._10";
  const tekst = "negatieve voorlopige aanslag: de aanslag tot een negatief bedrag;";
  const html = renderToStaticMarkup(createElement(KnoopTekst, {
    segmenten: [{ bron_iri: iri, type: "Onderdeel", label: "Onderdeel –", nummer: "–", tekst, bron_hash: "h", volgorde: 0 }],
    elementen: [], kiesbaar: () => false, onKies: () => {},
  }));
  expect(html.replace(/<[^>]*>/g, "")).toBe(`– ${tekst}`);
});
