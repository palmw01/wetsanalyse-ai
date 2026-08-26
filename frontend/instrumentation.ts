// Next.js instrumentation-hook: registreert OpenTelemetry (traces + metrics) via @vercel/otel.
// Gated op OTEL_EXPORTER_OTLP_ENDPOINT — zonder endpoint gebeurt er niets (geen overhead, geen
// dependency-lading). @vercel/otel instrumenteert automatisch de route handlers én uitgaande
// `fetch` (injecteert W3C-traceparent), zodat één trace de keten frontend → API → graph-qa omspant.
//
// LET OP — die belofte over de keten klopt op dit moment NIET, en dat faalt stil.
//
// Gemeten op acceptatie (26 aug 2026) met een eigen `traceparent`-header: deze kant doet het goed —
// de binnenkomende header wordt overgenomen en de spans nesten correct (`GET /api/health` →
// `executing api route` → de uitgaande fetch). Maar de api registreert diezelfde aanroep als een
// nieuwe root: in Application Insights heeft elke span daar `ParentId == OperationId`.
//
// `NEXT_OTEL_FETCH_DISABLED=1` staat inmiddels op de frontend (Azure: `deploy/azure/main.bicep`,
// docker-host: `deploy/dev/docker-compose.yml`). De Next.js-documentatie wijst die vlag aan wanneer
// je een eigen fetch-instrumentatie gebruikt, en @vercel/otel brengt er een mee — maar het lost het
// niet op. Openstaand: vaststellen of de traceparent de api überhaupt bereikt.
//
// Draait alleen in de nodejs-runtime (niet edge/middleware). Leest endpoint/protocol/service-name
// uit de standaard OTEL_*-env-vars.

export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;
  if (!process.env.OTEL_EXPORTER_OTLP_ENDPOINT) return;
  const { registerOTel } = await import("@vercel/otel");
  registerOTel({ serviceName: process.env.OTEL_SERVICE_NAME || "wetsanalyse-frontend" });
}
