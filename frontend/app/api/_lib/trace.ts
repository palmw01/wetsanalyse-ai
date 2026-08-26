// W3C-traceparent meesturen naar de upstream, zodat één trace de keten frontend → API → graph-qa
// omspant.
//
// Waarom dit met de hand gebeurt en niet automatisch: de instrumentatie in de frontend
// (`@vercel/otel`, en Next.js' eigen fetch-instrumentatie) maakt wél spans voor uitgaande calls,
// maar zet géén traceparent op de request. Gemeten met een echo-server achter `API_BASE_URL`: de
// upstream ontving `traceparent=None`. Gevolg was dat elke dienst zijn eigen losse traces
// registreerde — in Application Insights zichtbaar doordat elke span `ParentId == OperationId` had.
//
// `propagation.inject` is precies waar `@opentelemetry/api` voor bedoeld is en hangt niet af van
// welke instrumentatie er toevallig actief is. Zonder actieve span is het een no-op: dan blijven de
// headers ongemoeid en gebeurt er niets — ook als OTel helemaal uit staat.

import { context, propagation } from "@opentelemetry/api";

/** Geeft de headers terug met de traceparent van de lopende span erbij (of ongewijzigd). */
export function metTrace(headers: Record<string, string> = {}): Record<string, string> {
  const uit = { ...headers };
  propagation.inject(context.active(), uit);
  return uit;
}
