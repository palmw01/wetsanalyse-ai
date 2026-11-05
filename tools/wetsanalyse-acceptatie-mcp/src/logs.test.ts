import assert from "node:assert/strict";
import { test } from "node:test";
import { bouwQuery, rijen, zoekLogs } from "./logs.js";

test("alleen geldige ids komen in de query", () => {
  assert.match(bouwQuery({ trace_id: "a".repeat(32), minuten: 5 }), /OperationId == 'a{32}'/);
  assert.throws(() => bouwQuery({ trace_id: "' or 1==1", minuten: 5 }));
  assert.throws(() => bouwQuery({ run_id: "x' | take 1", minuten: 5 }));
  assert.match(bouwQuery({ minuten: 5 }), /'error'/);
});

test("frames worden rijen", () => {
  const frames = [{ schema: { fields: [{ name: "a" }, { name: "b" }] }, data: { values: [[1, 2], ["x", "y"]] } }];
  assert.deepEqual(rijen(frames), [{ a: 1, b: "x" }, { a: 2, b: "y" }]);
});

test("zoekLogs vraagt de workspace op en stuurt die mee", async () => {
  let verzonden: { queries: { azureLogAnalytics: { resources: string[] } }[] } | undefined;
  const nep = (async (url: string | URL, init?: RequestInit) => {
    if (String(url).endsWith("/api/datasources/uid/azmon-acceptatie")) {
      return Response.json({ jsonData: { logAnalyticsDefaultWorkspace: "/ws/acc" } });
    }
    verzonden = JSON.parse(String(init?.body));
    return Response.json({ results: { A: { frames: [] } } });
  }) as typeof fetch;
  const uit = await zoekLogs("http://g", "pw", { minuten: 10 }, nep);
  assert.deepEqual(uit.rijen, []);
  assert.deepEqual(verzonden?.queries[0].azureLogAnalytics.resources, ["/ws/acc"]);
});

test("een fout van Grafana wordt geen lege uitslag", async () => {
  const nep = (async (url: string | URL) =>
    String(url).includes("datasources")
      ? Response.json({ jsonData: { logAnalyticsDefaultWorkspace: "/ws/acc" } })
      : Response.json({ results: { A: { error: "kapot" } } })) as typeof fetch;
  await assert.rejects(zoekLogs("http://g", "pw", { minuten: 10 }, nep), /kapot/);
});
