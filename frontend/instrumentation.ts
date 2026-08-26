// Next.js instrumentation-hook: registreert OpenTelemetry (traces + metrics) via @vercel/otel.
// Gated op OTEL_EXPORTER_OTLP_ENDPOINT — zonder endpoint gebeurt er niets (geen overhead, geen
// dependency-lading). @vercel/otel instrumenteert automatisch de route handlers én uitgaande
// `fetch` (injecteert W3C-traceparent), zodat één trace de keten frontend → API → graph-qa omspant.
//
// LET OP — dat laatste werkt alleen met `NEXT_OTEL_FETCH_DISABLED=1` in de omgeving. Next.js
// instrumenteert `fetch` namelijk óók zelf: dat levert wél een span op, maar géén traceparent op de
// uitgaande request. De keten viel daardoor stil uiteen in losse traces per dienst — zichtbaar
// doordat elke span in Application Insights `ParentId == OperationId` had. De vlag zet die eigen
// instrumentatie uit zodat de undici-instrumentatie van @vercel/otel het overneemt; die injecteert
// de header wel. Op Azure staat de vlag in `deploy/azure/main.bicep`, op de docker-host in
// `deploy/dev/docker-compose.yml`.
//
// Draait alleen in de nodejs-runtime (niet edge/middleware). Leest endpoint/protocol/service-name
// uit de standaard OTEL_*-env-vars.

export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;
  if (!process.env.OTEL_EXPORTER_OTLP_ENDPOINT) return;
  const { registerOTel } = await import("@vercel/otel");
  registerOTel({ serviceName: process.env.OTEL_SERVICE_NAME || "wetsanalyse-frontend" });
}
