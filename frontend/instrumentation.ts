// Next.js instrumentation-hook: registreert OpenTelemetry (traces + metrics) via @vercel/otel.
// Gated op OTEL_EXPORTER_OTLP_ENDPOINT – zonder endpoint gebeurt er niets (geen overhead, geen
// dependency-lading). @vercel/otel instrumenteert automatisch de route handlers én uitgaande
// `fetch`, zodat de spans binnen de frontend correct nesten.
//
// LET OP – @vercel/otel injecteert die traceparent NIET op uitgaande fetch. Gemeten met een
// echo-server achter `API_BASE_URL` (26 aug 2026): de upstream kreeg `traceparent=None`, terwijl er
// in Application Insights wél nette uitgaande spans stonden. Een span is geen propagatie, en het
// verschil faalt stil: je ziet telemetrie, alleen elke dienst in zijn eigen trace.
//
// De BFF injecteert de header daarom zelf, expliciet, op elke fetch naar een upstream – zie
// `app/api/_lib/trace.ts`. Haal dat niet weg omdat de instrumentatie het "zou moeten doen".
//
// `NEXT_OTEL_FETCH_DISABLED=1` staat op de frontend (Azure: `deploy/azure/main.bicep`, docker-host:
// de compose-/app-config). Dat was een eerdere poging tot een fix en heeft niets opgelost;
// het staat er nog omdat de Next.js-documentatie de vlag aanwijst wanneer je een eigen
// fetch-instrumentatie gebruikt – wat nu letterlijk het geval is.
//
// Draait alleen in de nodejs-runtime (niet edge/middleware). Leest endpoint/protocol/service-name
// uit de standaard OTEL_*-env-vars.

export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;
  if (!process.env.OTEL_EXPORTER_OTLP_ENDPOINT) return;
  const { registerOTel } = await import("@vercel/otel");
  registerOTel({ serviceName: process.env.OTEL_SERVICE_NAME || "wetsanalyse-frontend" });
}
