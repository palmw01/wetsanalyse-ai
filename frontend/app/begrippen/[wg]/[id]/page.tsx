import { BegripPagina } from "@/components/werkgebieden/BegripPagina";

export const metadata = { title: "Begrip · Wetsanalyse" };

export default async function Pagina({ params }: { params: Promise<{ wg: string; id: string }> }) {
  const { wg, id } = await params;
  return <BegripPagina key={`${wg}/${id}`} werkgebiedId={wg} begripId={id} />;
}
