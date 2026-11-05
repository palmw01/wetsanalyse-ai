import { redirect } from "next/navigation";

import { begripPad } from "@/lib/werkgebiedPaden";

/** Een begrip woonde hier tot spoor N; bewaarde berichten en bladwijzers wijzen nog naar dit pad. */
export default async function Pagina({ params }: { params: Promise<{ wg: string; id: string }> }) {
  const { wg, id } = await params;
  redirect(begripPad(wg, id));
}
