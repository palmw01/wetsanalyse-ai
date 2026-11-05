import { BegripGeneriekPagina } from "@/components/begrippen/BegripGeneriekPagina";

export const metadata = { title: "Generiek begrip · Wetsanalyse" };

/** De pagina van een generiek begrip (ADR-006). Het segment heet `[wg]` omdat Next op één niveau maar één naam toestaat,
 *  en de doorverwijzing `[wg]/[id]` eronder hangt; hier is het een begrip-id. */
export default async function Pagina({ params }: { params: Promise<{ wg: string }> }) {
  const { wg: begripId } = await params;
  return <BegripGeneriekPagina key={begripId} begripId={begripId} />;
}
