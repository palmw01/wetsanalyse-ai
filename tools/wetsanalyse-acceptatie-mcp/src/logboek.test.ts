import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { aanvullen, lezen, standaardMap } from "./logboek.js";

async function metMap(doe: (map: string) => Promise<void>): Promise<void> {
  const map = await mkdtemp(join(tmpdir(), "logboek-"));
  try {
    await doe(map);
  } finally {
    await rm(map, { recursive: true });
  }
}

const basis = { run: "proef-1", rol: "jurist", soort: "beslissing", tekst: "Bron opgenomen." } as const;

test("aanvullen voegt toe en laat staan wat er stond", () =>
  metMap(async (map) => {
    const { pad } = await aanvullen(map, { ...basis, stap: 2, ids: ["e1"] }, new Date("2026-11-06T10:00:00Z"));
    await aanvullen(map, { ...basis, rol: "gegevensspecialist", soort: "overleg", tekst: "Akkoord." });
    const inhoud = await readFile(pad, "utf8");
    assert.equal(pad, join(map, "proef-1", "logboek.md"));
    assert.ok(inhoud.startsWith("### 2026-11-06T10:00:00Z · [jurist] · beslissing · stap 2\n\nBron opgenomen.\n\nids: e1\n\n"));
    assert.match(inhoud, /\[gegevensspecialist\] · overleg/);
  }));

test("twee agents tegelijk verliezen geen regels", () =>
  metMap(async (map) => {
    await Promise.all(Array.from({ length: 50 }, (_, i) => aanvullen(map, { ...basis, tekst: `regel ${i}` })));
    const { tekst } = await lezen(map, "proef-1");
    assert.equal(tekst.match(/^### /gm)?.length, 50);
  }));

test("een run kan niet buiten de map wijzen", () =>
  metMap(async (map) => {
    for (const run of ["../uit", "a/b", "..", "", "A B"]) {
      await assert.rejects(aanvullen(map, { ...basis, run }), /Een run heet/);
      await assert.rejects(lezen(map, run), /Een run heet/);
    }
  }));

test("een onenigheid vraagt beide argumenten", () =>
  metMap(async (map) => {
    await assert.rejects(aanvullen(map, { ...basis, soort: "onenigheid" }), /beide argumenten/);
    await assert.rejects(
      aanvullen(map, { ...basis, soort: "onenigheid", argumenten: { jurist: "ja", gegevensspecialist: " " } }),
      /beide argumenten/,
    );
    await aanvullen(map, { ...basis, soort: "onenigheid", argumenten: { jurist: "ja", gegevensspecialist: "nee" } });
    assert.match((await lezen(map, "proef-1")).tekst, /- jurist: ja\n- gegevensspecialist: nee/);
  }));

test("een token komt niet in het logboek", () =>
  metMap(async (map) => {
    await assert.rejects(aanvullen(map, { ...basis, tekst: "token wa_pat_abc" }), /token/);
    await assert.rejects(aanvullen(map, { ...basis, ids: ["Bearer abc"] }), /token/);
    assert.equal((await lezen(map, "proef-1")).tekst, "");
  }));

test("lezen geeft alleen het nieuwe, ook met letters buiten ASCII", () =>
  metMap(async (map) => {
    assert.deepEqual(await lezen(map, "proef-1"), { tekst: "", vanaf: 0 });
    await aanvullen(map, { ...basis, tekst: "één" });
    const eerst = await lezen(map, "proef-1");
    await aanvullen(map, { ...basis, tekst: "twee" });
    const daarna = await lezen(map, "proef-1", eerst.vanaf);
    assert.doesNotMatch(daarna.tekst, /één/);
    assert.match(daarna.tekst, /twee/);
  }));

test("het logboek staat bij het dossier, ook vanuit een worktree", () => {
  const verwacht = join("/p/repo", "docs", "acceptatie", "lokaal");
  assert.equal(standaardMap("/p/repo/"), verwacht);
  assert.equal(standaardMap("/p/repo/.claude/worktrees/naam/"), verwacht);
});
