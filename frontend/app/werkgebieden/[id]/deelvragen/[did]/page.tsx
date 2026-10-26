import { DeelvraagPagina } from "@/components/werkgebieden/DetailPaginas";

export default async function Pagina({ params }: { params: Promise<{ did: string }> }) {
  const { did } = await params;
  return <DeelvraagPagina deelvraagId={did} />;
}
