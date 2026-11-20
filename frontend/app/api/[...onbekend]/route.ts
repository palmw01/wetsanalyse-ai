/**
 * Elk `/api/`-pad dat geen eigen route heeft: een 404 als JSON, niet de HTML-pagina van Next (~15k tekens). Een
 * MCP-client of agent die een pad verkeerd raadt, krijgt zo een leesbare fout (Termijnen e2e, 20 nov 2026). Een
 * statisch of dynamisch segment gaat in Next altijd vóór deze catch-all, dus bestaande routes merken er niets van.
 */
export const dynamic = "force-dynamic";

function onbekend(req: Request): Response {
  return Response.json({ detail: "Onbekende route.", pad: new URL(req.url).pathname }, { status: 404 });
}

export const GET = onbekend;
export const POST = onbekend;
export const PUT = onbekend;
export const PATCH = onbekend;
export const DELETE = onbekend;
