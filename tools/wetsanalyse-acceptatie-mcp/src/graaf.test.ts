import assert from "node:assert/strict";
import { test } from "node:test";
import { controleerSparql, GraafClient, leesRpc } from "./graaf.js";

test("leesvormen gaan door, met een LIMIT als die ontbreekt", () => {
  assert.equal(controleerSparql("SELECT ?s WHERE { ?s ?p ?o } LIMIT 5"), "SELECT ?s WHERE { ?s ?p ?o } LIMIT 5");
  assert.equal(controleerSparql("SELECT ?s WHERE { ?s ?p ?o } OFFSET 2 LIMIT 5").endsWith("LIMIT 5"), true);
  assert.equal(controleerSparql("ASK { ?s ?p ?o }"), "ASK { ?s ?p ?o }");
  assert.match(controleerSparql("PREFIX ex: <urn:x#>\nBASE <urn:y>\nSELECT * { ?s ?p ?o } # einde"), /# einde\nLIMIT 200$/);
  // een LIMIT in een subquery begrenst de buitenste query niet
  assert.match(controleerSparql("SELECT * { { SELECT ?s { ?s ?p ?o } LIMIT 1 } ?s ?q ?r }"), /LIMIT 200$/);
});

test("woorden in tekst, IRI's, namen en commentaar zijn geen update", () => {
  for (const q of [
    `SELECT * { ?s ?p "delete insert drop" }`,
    `SELECT * { ?s <urn:x:delete> ?o }`,
    `PREFIX ex: <urn:x#> SELECT ?add { ?add ex:move ex:copy }`,
    `SELECT * { ?s ?p ?o } # delete dit later`,
  ]) {
    controleerSparql(q);
  }
});

test("updates, onbekende vormen en federatie worden geweigerd", () => {
  for (const q of [
    "INSERT DATA { <a:a> <b:b> <c:c> }",
    "DELETE WHERE { ?s ?p ?o }",
    "PREFIX ex: <urn:x#> DELETE { ?s ?p ?o } WHERE { ?s ?p ?o }",
    "DROP GRAPH <urn:g>",
    "CLEAR ALL",
    "LOAD <http://x>",
    "SELECT * { ?s ?p ?o } ; DROP ALL",
    "SELECT * { SERVICE <http://intern/> { ?s ?p ?o } }",
    "# SELECT\nDROP ALL",
    "",
  ]) {
    assert.throws(() => controleerSparql(q), Error, q);
  }
});

test("rpc: SSE zonder spatie, gewone JSON, en een fout blijft een fout", () => {
  assert.deepEqual(leesRpc('event: message\ndata:{"result":{"a":1}}\n\n', "text/event-stream"), { a: 1 });
  assert.deepEqual(leesRpc('{"result":{"a":1}}', "application/json"), { a: 1 });
  assert.throws(() => leesRpc('{"error":{"message":"kapot"}}', "application/json"), /kapot/);
  assert.throws(() => leesRpc("<html>", "text/html"), /Geen bruikbaar/);
});

function nepGraaf(antwoorden: (Response | undefined)[]) {
  const methodes: string[] = [];
  const headers: Record<string, string>[] = [];
  const nep = (async (_: string | URL, init?: RequestInit) => {
    const { method } = JSON.parse(String(init?.body)) as { method: string };
    methodes.push(method);
    headers.push(init?.headers as Record<string, string>);
    if (method === "initialize") {
      return new Response('{"result":{}}', { headers: { "Mcp-Session-Id": `s${methodes.length}`, "content-type": "application/json" } });
    }
    return antwoorden.shift() ?? assert.fail("te veel aanroepen");
  }) as typeof fetch;
  return { nep, methodes, headers };
}

const tsv = (t: string) =>
  new Response(`data:${JSON.stringify({ result: { content: [{ type: "text", text: JSON.stringify(t) }] } })}\n\n`, {
    headers: { "content-type": "text/event-stream" },
  });

test("lees: handdruk eerst, sessie mee, en de TSV uitgepakt", async () => {
  const { nep, methodes, headers } = nepGraaf([tsv("?s\n<urn:a>\n")]);
  const uit = await new GraafClient("http://g", "geheim", nep).lees("SELECT ?s { ?s ?p ?o }");
  assert.equal(uit.uitslag, "?s\n<urn:a>\n");
  assert.equal(uit.afgekapt, false);
  assert.match(uit.query, /LIMIT 200$/);
  assert.deepEqual(methodes, ["initialize", "tools/call"]);
  assert.equal(headers[1].Authorization, "Bearer geheim");
  assert.equal(headers[1]["Mcp-Session-Id"], "s1");
});

test("lees: een verlopen sessie krijgt één nieuwe handdruk", async () => {
  const { nep, methodes } = nepGraaf([new Response("", { status: 404 }), tsv("?s\n")]);
  await new GraafClient("http://g", "t", nep).lees("ASK { ?s ?p ?o }");
  assert.deepEqual(methodes, ["initialize", "tools/call", "initialize", "tools/call"]);
});

test("lees: een geweigerde query wordt niet verstuurd, en een toolfout geen lege uitslag", async () => {
  const stil = (async () => assert.fail("geen aanroep verwacht")) as typeof fetch;
  await assert.rejects(new GraafClient("http://g", "t", stil).lees("DROP ALL"));
  const fout = new Response('{"result":{"isError":true,"content":[{"text":"syntax"}]}}', { headers: { "content-type": "application/json" } });
  await assert.rejects(new GraafClient("http://g", "t", nepGraaf([fout]).nep).lees("ASK { ?s ?p ?o }"), /syntax/);
});
