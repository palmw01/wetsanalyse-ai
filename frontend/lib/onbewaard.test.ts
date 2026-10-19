import { describe, expect, it } from "vitest";

import { verlaatPagina } from "./onbewaard";

const hier = { origin: "https://wa.example", pathname: "/werkgebieden/w1", search: "?tab=begrippen&begrip=b1" };

describe("verlaatPagina", () => {
  it("een link naar een andere pagina in de app verlaat de pagina", () => {
    expect(verlaatPagina("/begrippen", hier)).toBe(true);
    expect(verlaatPagina("/workbench?werkgebied=w1", hier)).toBe(true);
    expect(verlaatPagina("/werkgebieden", hier)).toBe(true);
  });

  it("dezelfde pagina met een andere query ook", () => {
    expect(verlaatPagina("/werkgebieden/w1?tab=elementen", hier)).toBe(true);
  });

  it("dezelfde pagina of alleen een anker niet", () => {
    expect(verlaatPagina("/werkgebieden/w1?tab=begrippen&begrip=b1", hier)).toBe(false);
    expect(verlaatPagina("#passages", hier)).toBe(false);
  });

  it("het instellingenvenster opent over de pagina heen", () => {
    expect(verlaatPagina("/instellingen/account", hier)).toBe(false);
  });

  it("een andere origin laat hij aan beforeunload over", () => {
    expect(verlaatPagina("https://wetten.overheid.nl/BWBR0004770", hier)).toBe(false);
  });
});
