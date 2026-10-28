import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, it } from "vitest";

import { themaGroepen, themaLabel } from "./tooiThemas";

it("de thema's zijn gelijk aan de snapshot van de api", () => {
  const api = readFileSync(join(__dirname, "../../api/app/tooi_themas.json"), "utf8");
  const hier = readFileSync(join(__dirname, "tooi-themas.json"), "utf8");
  expect(JSON.parse(hier)).toEqual(JSON.parse(api));
});

it("groepeert per hoofdthema en kent de naam", () => {
  const groepen = themaGroepen();
  const fin = groepen.find((g) => g.hoofd.label === "overheidsfinanciën");
  expect(fin?.subs.map((s) => s.label)).toEqual(["begroting", "belasting"]);
  expect(themaLabel("https://identifier.overheid.nl/tooi/def/thes/top/c_25e30d03")).toBe("belasting");
  expect(themaLabel("x")).toBe("");
});
