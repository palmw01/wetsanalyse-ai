import { notFound } from "next/navigation";
import { graafMockAan } from "@/lib/graafMockGate";
import { GraafMockWorkbench } from "@/components/graaf/GraafMockWorkbench";

export const metadata = { title: "3D-workbench · Interactieve mock" };
export const dynamic = "force-dynamic";

export default function GraafMockPagina() {
  if (!graafMockAan()) notFound();
  return <GraafMockWorkbench />;
}
