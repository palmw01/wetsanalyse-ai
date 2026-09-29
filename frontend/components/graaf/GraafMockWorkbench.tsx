"use client";

import { useCallback, useMemo, useState } from "react";
import { AppSidebar } from "@/components/werkplek/AppSidebar";
import { MobieleTopbar } from "@/components/werkplek/MobieleTopbar";
import { WerkplekClient } from "@/components/werkplek/WerkplekClient";
import { Dialog } from "@/components/ui/Dialog";
import { LokaleMockContext } from "./LokaleMockContext";
import { maakGraafScene, type GraafScenario } from "@/lib/graafMock";

export function GraafMockWorkbench() {
  const [scenario, setScenario] = useState<GraafScenario>("bronnen");
  const [versie, setVersie] = useState(0);
  const [drawer, setDrawer] = useState(false);
  const [melding, setMelding] = useState("");
  const scene = useMemo(() => maakGraafScene(scenario), [scenario]);
  const meld = useCallback((tekst: string) => setMelding(tekst), []);
  function kies(id: string) {
    setScenario(id === "annotaties" ? "annotaties" : id === "nieuw" ? "nieuw" : "bronnen");
    setVersie((n) => n + 1);
    setDrawer(false);
  }
  return <LokaleMockContext.Provider value={meld}>
      <div className="flex h-[100dvh] flex-col overflow-hidden bg-paper" onClickCapture={(event) => {
        const link = (event.target as HTMLElement).closest<HTMLAnchorElement>("a[href]");
        if (!link) return;
        const url = new URL(link.href);
        if (url.origin !== location.origin) return;
        event.preventDefault();
        if (url.pathname === "/annotaties") kies("annotaties");
        else if (["/", "/workbench"].includes(url.pathname)) kies("bronnen");
        else meld("Deze mock laat de chat, annotaties en 3D-graaf zien. Overige onderdelen open je in de echte workbench.");
      }}>
        <div className="flex shrink-0 items-center justify-center gap-3 border-b border-waarschuwing/10 bg-waarschuwing/10 px-3 py-1.5 text-[11px] text-ink">
          <span><strong>Interactieve mock</strong><span className="hidden sm:inline"> · 3D-graaf in de workbench · voorbeeldgegevens</span></span>
          <button type="button" className="focus-ring shrink-0 rounded underline underline-offset-2" onClick={() => kies("bronnen")}>Herstel voorbeelden</button>
        </div>
        <div className="flex min-h-0 flex-1">
          <AppSidebar key={`sidebar-${versie}`} activeId={scenario === "nieuw" ? null : scenario}
            onNieuw={() => kies("nieuw")} onOpen={kies} onVerwijderd={() => kies("nieuw")}
            demoGesprekken={scene.gesprekken} drawerOpen={drawer} onDrawerSluit={() => setDrawer(false)} />
          <main className="flex min-h-0 min-w-0 flex-1 flex-col">
            <MobieleTopbar titel="Lex · 3D-workbench" onOpenSidebar={() => setDrawer(true)} />
            <WerkplekClient key={`${scenario}-${versie}`} initialGesprekId={null}
              onGesprekAangemaakt={() => {}} onGewijzigd={() => {}} demo={scene}
              graafMock={scenario} />
          </main>
        </div>
        {melding && <Dialog label="Over deze mock" variant="compact" onSluit={() => setMelding("")}>
          <div className="space-y-4 p-6"><h2 className="text-lg font-semibold">Over deze mock</h2><p className="text-sm text-muted">{melding}</p>
            <button className="focus-ring rounded-button bg-lint px-4 py-2 text-sm text-white" onClick={() => setMelding("")}>Terug naar de mock</button>
          </div>
        </Dialog>}
      </div>
    </LokaleMockContext.Provider>;
}
