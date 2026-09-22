import { NodeAnnotatiePaneel } from "@/components/annotaties/NodeAnnotatiePaneel";

export const metadata = { title: "Annotatie · Wetsanalyse" };
export default async function NodeAnnotatiePagina({ searchParams }: {
  searchParams: Promise<{ bron_iri?: string; snapshot_id?: string }>;
}) {
  const { bron_iri, snapshot_id } = await searchParams;
  if (!bron_iri) return <p>De bronnode ontbreekt in deze link.</p>;
  return <main className="mx-auto max-w-5xl"><NodeAnnotatiePaneel doel={{ bron_iri, snapshot_id }} /></main>;
}
