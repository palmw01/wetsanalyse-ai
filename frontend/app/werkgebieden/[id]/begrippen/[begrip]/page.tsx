import { BegripPagina } from "@/components/werkgebieden/BegripPagina";

export const metadata = { title: "Begrip · Wetsanalyse" };

export default async function Pagina({ params }: { params: Promise<{ begrip: string }> }) {
  const { begrip } = await params;
  return <BegripPagina key={begrip} begripId={begrip} />;
}
