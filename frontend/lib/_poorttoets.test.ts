// Wegwerpbestand: toetst dat de CI-poort een falende test daadwerkelijk tegenhoudt.
import { describe, expect, it } from "vitest";
describe("poort-toets", () => { it("moet falen", () => { expect(1).toBe(2); }); });
