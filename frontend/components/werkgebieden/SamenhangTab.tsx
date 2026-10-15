"use client";

import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { Graaf, type GraafContext } from "@/components/graaf/Graaf";
import { useGraafStand } from "@/components/graaf/useGraafStand";
import type { Mutatie } from "@/components/werkgebieden/WerkgebiedClient";
import { voegBronToe } from "@/lib/api";
import { isBron, type KnoopData } from "@/lib/graaf/model";
import type { BronRol, Werkgebied } from "@/lib/types";
import { ROL_LABEL, annotatieHref, scopeInModel } from "@/lib/werkgebied";

const WERKGEBIED: GraafContext = {
  naam: "Dit werkgebied", kort: "Werkgebied", terug: "het werkgebied", focus: "de bronnen van dit werkgebied",
};

const KNOP =
  "focus-ring inline-flex min-h-[24px] items-center rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-lint transition-colors hover:bg-surface disabled:opacity-50 coarse:min-h-[44px]";

/** De samenhang van het werkgebied: de bestaande samenhangsgraaf met de bronselecties als doelen.
 *  Opnemen kan vanuit de inspector, altijd met een rol; een niet-geïmporteerde bepaling is niet op te
 *  nemen. Wat er verder bij kan horen, zoekt Lex op de tab Bronnen (fase A). */
export function SamenhangTab({ wg, muteer }: { wg: Werkgebied; muteer: Mutatie }) {
  if (wg.bronnen.length === 0)
    return <p className="text-sm text-muted">Nog geen bronnen, dus nog geen samenhang. Neem eerst een bepaling op.</p>;
  // Opnieuw laden als de verzameling bronnen verandert; een andere rol of reden verandert de kaart niet.
  const sleutel = wg.bronnen.map((b) => `${b.bron_iri}:${b.bereik}`).sort().join("|");
  return <SamenhangGraaf key={sleutel} wg={wg} muteer={muteer} />;
}

function SamenhangGraaf({ wg, muteer }: { wg: Werkgebied; muteer: Mutatie }) {
  const router = useRouter();
  // Stabiele doelen: `useGraafStand` laadt opnieuw zodra het doel een ander object is. De bronnen zelf
  // veranderen hier niet (de ouder geeft een nieuwe `key` als ze dat wel doen).
  const { doel, extra, opties, doelen } = useMemo(() => {
    const [eerste, ...rest] = wg.bronnen;
    const doelen = wg.bronnen.map((b) => b.bron_iri);
    return {
      doel: { bron_iri: eerste.bron_iri, label: eerste.label },
      extra: rest.map((b) => ({ bron_iri: b.bron_iri, label: b.label })),
      opties: { focus: doelen },
      doelen,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const stand = useGraafStand(doel, true, true, extra, opties);
  const model = stand.getekend?.model;
  const scope = useMemo(() => (model ? scopeInModel(model, wg.bronnen) : new Set<string>()), [model, wg.bronnen]);

  function neemOp(bronIri: string, naam: string, rol: BronRol) {
    return muteer(async (r) => (await voegBronToe(wg.id, { bron_iri: bronIri, rol, verwachte_revisie: r })).werkgebied, {
      gelukt: `${naam} opgenomen als ${ROL_LABEL[rol].toLowerCase()}.`,
    });
  }

  function opneemActie(k: KnoopData & { id: string }) {
    if (!isBron(k) || k.soort === "regeling") return null;
    if (doelen.includes(k.id)) return <span className="text-[11px] text-muted">Staat in dit werkgebied</span>;
    if (scope.has(k.id)) return <span className="text-[11px] text-muted">Valt binnen dit werkgebied</span>;
    if (k.soort === "extern" || !k.bwb_id) return <span className="text-[11px] text-muted">Niet in de graaf, niet op te nemen</span>;
    return (
      <>
        <button type="button" className={KNOP} onClick={() => void neemOp(k.id, k.naam, "analyseren")}>
          Opnemen in werkgebied
        </button>
        <button type="button" className={KNOP} onClick={() => void neemOp(k.id, k.naam, "context")}>
          Als contextbron
        </button>
      </>
    );
  }

  return (
    <div>
      {/* De graaf vult zijn doos; zonder vaste hoogte heeft het canvas er geen. */}
      <div className="flex h-[70vh] min-h-[28rem] flex-col overflow-hidden rounded-button border border-line bg-paper">
        <Graaf
          stand={stand}
          zichtbaar
          groot
          onKiesElement={() => {}}
          onOpenTekst={(k, anker) => router.push(annotatieHref(anker ?? k.id))}
          benaming={WERKGEBIED}
          bijKnoop={opneemActie}
        />
      </div>
    </div>
  );
}
