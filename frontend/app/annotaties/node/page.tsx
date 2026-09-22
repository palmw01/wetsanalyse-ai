import { AnnotatiePaginaSchil } from "@/components/annotaties/AnnotatiePaginaSchil";
import { NodeAnnotatiePaneel } from "@/components/annotaties/NodeAnnotatiePaneel";
import { Melding } from "@/components/ui/Melding";

export const metadata = { title: "Annotatie · Wetsanalyse" };

/** Een bronnode-annotatie als eigen pagina – dezelfde schil als `/annotaties/<slug>`. */
export default async function NodeAnnotatiePagina({ searchParams }: {
  searchParams: Promise<{ bron_iri?: string; snapshot_id?: string }>;
}) {
  const { bron_iri, snapshot_id } = await searchParams;
  return (
    <AnnotatiePaginaSchil titel="Annotatie">
      {bron_iri ? (
        <NodeAnnotatiePaneel doel={{ bron_iri, snapshot_id }} />
      ) : (
        <div className="p-5">
          <Melding type="uitleg">De bronnode ontbreekt in deze link.</Melding>
        </div>
      )}
    </AnnotatiePaginaSchil>
  );
}
