/** Wat het bronvenster opent (het bronvenster-plan, PR 1): een bron, niet alleen een BWB-bepaling. Een bepaling uit de
 *  kennisgraaf en een stuk uit een bronconnector (ADR-013: Kamerstukken, straks Rechtspraak) zijn twee soorten van één doel,
 *  met dezelfde kop, tabbalk en blokken. Niets hier kent een connector bij naam: welke er zijn, hoe hun id's eruitzien en
 *  welke metadata ze dragen, komt uit het register (`bronmodel.connectors`). Het stuk zelf opent pas in PR 6. */
export type BronDoel =
  | {
      soort: "bepaling";
      bron_iri: string;
      /** De jci die Lex las, met de toestand (`&g=`): wijkt de graaf af, dan zegt het venster dat. */
      jci?: string;
      /** Het werkgebied waarin de bepaling geopend is: dan telt zijn peildatum. */
      werkgebied_id?: string;
    }
  | {
      soort: "stuk";
      /** De naam van de connector in het register. */
      connector: string;
      /** Het id zoals de connector het kent, bv. "kst-35496-F". */
      id: string;
      /** Wat Lex las: de hash van de lezing en de passages die hij citeerde. */
      gelezen?: { bron_hash: string; passages: string[] };
    };
