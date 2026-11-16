import assert from "node:assert/strict";
import { test } from "node:test";
import type { BffAntwoord } from "./client.js";
import { KETEN, ketenScenario } from "./keten.js";

interface Rij { id: string; [k: string]: unknown }

/** Een nep-BFF met het account van de gebruiker: eigen gesprekken en een werkgebied, en wat er verwijderd werd. */
function account(opties: { weigerDelete?: boolean } = {}) {
  const werkgebieden: Rij[] = [{ id: "w-eigen", naam: "Verrekening", aangemaakt_door: "palm", revisie: 4 }];
  const gesprekken: Rij[] = [{ id: "g-eigen", titel: "Mijn meting van gisteren", werkgebied_id: "", ouder_id: "" }];
  const aanroepen: string[] = [];
  let n = 0;
  const ant = (status: number, data: unknown = null): BffAntwoord => ({ status, trace_id: "", data });
  return {
    werkgebieden, gesprekken, aanroepen,
    async bff(methode: string, pad: string, body?: unknown): Promise<BffAntwoord> {
      aanroepen.push(`${methode} ${pad}`);
      const [kaal] = pad.split("?");
      const [, , soort, id] = kaal.split("/");
      if (kaal === "/api/account/me") return ant(200, { userid: "palm" });
      const bak = soort === "werkgebieden" ? werkgebieden : gesprekken;
      if (methode === "GET" && !id) return ant(200, soort === "werkgebieden" ? { werkgebieden } : gesprekken);
      if (methode === "POST" && !id) {
        const rij = { id: `${soort[0]}${++n}`, werkgebied_id: "", ouder_id: "", aangemaakt_door: "palm", revisie: 1,
          ...(body as object) };
        bak.push(rij);
        return ant(201, rij);
      }
      const i = bak.findIndex((r) => r.id === id);
      if (methode === "GET") return i < 0 ? ant(404) : ant(200, bak[i]);
      if (methode === "DELETE") {
        if (opties.weigerDelete) return ant(500);
        bak.splice(i, 1);
        return ant(204);
      }
      return ant(405);
    },
  };
}

test("[R19] het ketenscenario maakt, leest en ruimt alleen zijn eigen objecten op", async () => {
  const a = account();
  const uit = await ketenScenario(a, "123-1");
  assert.ok(uit.ok, JSON.stringify(uit.stappen));
  assert.deepEqual(a.werkgebieden.map((w) => w.id), ["w-eigen"]);
  assert.deepEqual(a.gesprekken.map((g) => g.id), ["g-eigen"]);
  const deletes = a.aanroepen.filter((x) => x.startsWith("DELETE") || x.includes("/verwijderen"));
  assert.equal(deletes.length, 2, deletes.join("\n"));
  assert.ok(deletes.every((x) => !x.includes("eigen")), "geen DELETE op iets van de gebruiker");
  assert.ok(a.werkgebieden.concat(a.gesprekken).every((r) => !String(r.naam ?? r.titel).startsWith(KETEN)));
});

test("[R19] een mislukte stap ruimt alleen op wat de run maakte, en is nooit groen", async () => {
  const a = account({ weigerDelete: true });
  const uit = await ketenScenario(a, "123-2");
  assert.equal(uit.ok, false);
  assert.ok(uit.stappen.some((s) => !s.ok && s.stap === "opruimen"));
  assert.ok(!a.aanroepen.some((x) => x.startsWith("DELETE") && x.includes("eigen")), "nooit iets van de gebruiker");
});
