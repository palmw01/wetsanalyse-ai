"use client";

import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { useCallback, useEffect, useState } from "react";
import { knopKlasse, KNOP_GEVAAR_SCHERP } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Melding } from "@/components/ui/Melding";
import { SettingGroup } from "@/components/ui/SettingRow";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { Pagination } from "@/components/Pagination";
import { getFeedback, isApiError, markeerFeedbackGezien, verwijderFeedback } from "@/lib/api";
import type { FeedbackPaginaOut } from "@/lib/api";
import { datumTijd } from "@/lib/datum";
import { StatusLabel } from "@/components/ui/Lijst";

const CATEGORIE_LABELS: Record<string, string> = {
  verbeteridee: "Verbeteridee",
  probleemmelding: "Probleemmelding",
  compliment: "Compliment",
  vraag: "Vraag",
};

const PER_PAGINA = 50;

export function FeedbackLijstClient() {
  const [data, setData] = useState<FeedbackPaginaOut | null>(null);
  const [pagina, setPagina] = useState(1);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState<number | null>(null);

  const laad = useCallback(async (p: number) => {
    setFout(null);
    try {
      const result = await getFeedback((p - 1) * PER_PAGINA, PER_PAGINA);
      setData(result);
      if (p === 1) {
        // Nieuwste item staat vooraan (created.desc()); markeer pas ná het tonen en tot dat
        // moment – niet tot "nu" – zodat feedback die tussen laden en markeren binnenkomt
        // niet ten onrechte als gezien telt (was: twee gelijktijdige requests met dat risico).
        const tot = result.items[0]?.created;
        void markeerFeedbackGezien(tot).catch(() => { /* stil falen */ });
      }
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
    }
  }, []);

  useEffect(() => {
    // De setState zit ín de async callback, dus pas ná het await – geen synchrone cascading
    // render. De regel kan daar niet doorheen kijken.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laad(1);
  }, [laad]);

  function onPage(p: number) {
    setPagina(p);
    void laad(p);
  }

  // Bevestigen doet de knop zelf (twee klikken), zoals overal in deze app.
  async function onVerwijder(id: number) {
    setBezig(id);
    try {
      await verwijderFeedback(id);
      setData((prev) =>
        prev ? { items: prev.items.filter((i) => i.id !== id), totaal: prev.totaal - 1 } : null,
      );
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
    } finally {
      setBezig(null);
    }
  }

  return (
    <SettingGroup titel="Feedback" count={data?.totaal} omschrijving="Wat analisten via de feedbackknop instuurden.">
      {fout && <Melding type="fout" className="mb-3">{fout}</Melding>}
      {data === null ? (
        <SkeletonCard regels={2} />
      ) : data.items.length === 0 ? (
        <p className="text-sm text-muted">Nog geen feedback ingezonden.</p>
      ) : (
        <div className="space-y-3">
          {data.items.map((item) => (
            <Card key={item.id} className="p-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-mono text-xs text-faint">#{item.id}</span>
                <StatusLabel toon="lint">{CATEGORIE_LABELS[item.categorie] ?? item.categorie}</StatusLabel>
                <span className="text-xs text-muted">{item.userid}</span>
                <span className="text-xs text-faint">client: {item.client_id}</span>
                <span className="ml-auto text-xs text-faint">{datumTijd(item.created)}</span>
                <BevestigKnop
                  onBevestig={() => void onVerwijder(item.id)}
                  disabled={bezig === item.id}
                  ariaLabel={`Feedbackbericht #${item.id} verwijderen`}
                  bevestigTekst="Verwijderen?"
                  className={knopKlasse("danger", "xs")}
                  bevestigClassName={KNOP_GEVAAR_SCHERP}
                >
                  {bezig === item.id ? "…" : "Verwijderen"}
                </BevestigKnop>
              </div>
              {item.pagina && (
                <p className="mt-2 text-xs text-muted">
                  <span className="font-medium text-ink">Pagina:</span>{" "}
                  <span className="font-mono">{item.pagina}</span>
                </p>
              )}
              <p className="mt-2 whitespace-pre-wrap text-sm text-ink">{item.tekst}</p>
            </Card>
          ))}
        </div>
      )}
      {data !== null && (
        <Pagination
          page={pagina}
          totalPages={Math.max(1, Math.ceil(data.totaal / PER_PAGINA))}
          total={data.totaal}
          pageSize={PER_PAGINA}
          onPage={onPage}
        />
      )}
    </SettingGroup>
  );
}
