import { ElementPagina } from "@/components/annotaties/ElementPagina";

export const metadata = { title: "JAS-element · Wetsanalyse" };

export default async function Pagina({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ElementPagina key={id} id={id} />;
}
