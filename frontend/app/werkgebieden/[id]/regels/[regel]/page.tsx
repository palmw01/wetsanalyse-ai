import { RegelPagina } from "@/components/werkgebieden/RegelPagina";

export const metadata = { title: "Afleidingsregel · Wetsanalyse" };

export default async function Pagina({ params }: { params: Promise<{ regel: string }> }) {
  const { regel } = await params;
  return <RegelPagina key={regel} regelId={regel} />;
}
