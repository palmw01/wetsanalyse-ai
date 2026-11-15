"use client";

import { Leeg } from "@/components/ui/Leeg";
import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";

import { AanpassingDetail, AanpassingLijst, useLijstStand } from "@/components/instellingen/AanpassingLijst";
import { HerkomstKaart, tekst, useCatalogus, useOnderdeel } from "@/components/instellingen/OnderdeelKaarten";
import { Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Regel, Regels, StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Kaart } from "@/components/ui/Pagina";
import { Skeleton } from "@/components/ui/Skeleton";
import { connectorAudit, foutTekst, getAccount, haalConnectors, listConnectors, zetConnector } from "@/lib/api";
import type { Onderdeel } from "@/lib/catalogus";
import { naamVan } from "@/lib/catalogus";
import { datumTijd } from "@/lib/datum";
import { kiesInstellingenTab } from "@/lib/instellingenVenster";
import type { Connector, ConnectorAuditRegel } from "@/lib/types";

/** Instellingen › Aanpassingen › Connectors (ADR-013, plan instellingen-aanpassingen): de bronnen buiten de wettekst die
 *  Lex mag raadplegen, voor iedereen in één lijst. Welke er bestaan staat in de code; een beheerder met 2FA zet ze hier
 *  aan of uit (elke wijziging staat in de audit). Aan betekent: beschikbaar in het menu bij het gesprek; de straat moet
 *  hem ook aanbieden (`CONNECTOR_*`). Een analist ziet dezelfde lijst zonder knop. */
export function ConnectorsPanel() {
  const { data: sessie } = useSession();
  const beheerder = sessie?.user?.role === "beheerder";
  const lijst = useLijstStand(false);
  const catalogus = useCatalogus();
  const [beheer, setBeheer] = useState<Connector[] | null>(null);
  const [aan, setAan] = useState<string[] | null>(null);
  const [tfaNodig, setTfaNodig] = useState(false);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState<string | null>(null);

  const laad = useCallback(async () => {
    setFout(null);
    try {
      if (beheerder) {
        const [account, alle] = await Promise.all([getAccount(), listConnectors()]);
        setTfaNodig(account.tfa_nodig);
        setBeheer(alle);
      } else {
        setAan((await haalConnectors()).aan);
      }
    } catch (e) {
      setFout(foutTekst(e, "De stand van de connectors kon niet worden geladen."));
    }
  }, [beheerder]);

  useEffect(() => {
    // Data-load bij mount: setState gebeurt async ná de fetch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (sessie) void laad();
  }, [laad, sessie]);

  async function wissel(c: Connector) {
    setBezig(c.naam);
    setFout(null);
    try {
      const nieuw = await zetConnector(c.naam, !c.aan);
      setBeheer((oud) => oud?.map((x) => (x.naam === nieuw.naam ? nieuw : x)) ?? null);
    } catch (e) {
      setFout(foutTekst(e, "De connector kon niet worden omgezet."));
    } finally {
      setBezig(null);
    }
  }

  // De catalogus beschrijft wat een bron dekt; de stand komt van de api. Een beheerder ziet ook een connector die de
  // catalogus (nog) niet kent, zodat hij hem altijd kan uitzetten.
  const uitCatalogus = catalogus.data?.onderdelen.filter((o) => o.soort === "connector") ?? [];
  const namen = [...new Set([...uitCatalogus.map((o) => naamVan(o.id)), ...(beheer ?? []).map((c) => c.naam)])];
  const rijen = namen.map((naam) => {
    const o = uitCatalogus.find((x) => naamVan(x.id) === naam);
    const c = beheer?.find((x) => x.naam === naam);
    const isAan = c ? c.aan : (aan ?? []).includes(naam);
    const label = c?.label ?? o?.label ?? naam;
    return {
      id: `connector/${naam}`, naam: label, titel: label, zoektekst: `${label} ${o?.doel ?? ""} ${c?.beschrijving ?? ""} ${naam}`,
      onOpen: () => lijst.open(`connector/${naam}`),
      sub: [c?.beschrijving || o?.doel, c?.door && `${c.aan ? "Aangezet" : "Uitgezet"} door ${c.door}${c.bijgewerkt ? `, ${datumTijd(c.bijgewerkt)}` : ""}`]
        .filter(Boolean).join(" · "),
      status: <>
        {(beheer || aan) && <StatusLabel toon={isAan ? "groen" : "neutraal"}>{isAan ? "Aan" : "Uit"}</StatusLabel>}
        {c?.brontype && <Tag>{c.brontype}</Tag>}
        {o && !o.aan && <StatusLabel>hier niet aangeboden</StatusLabel>}
      </>,
      eind: c && !tfaNodig ? (
        <Button size="sm" variant={c.aan ? "secondary" : "primary"} disabled={bezig === c.naam} onClick={() => wissel(c)}>
          {bezig === c.naam ? "Bezig…" : c.aan ? "Uitzetten" : "Aanzetten"}</Button>
      ) : undefined,
      data: { "data-connector": naam },
    };
  });
  const open = lijst.onderdeel?.startsWith("connector/") ? lijst.onderdeel : null;

  return (
    <AanpassingLijst
      titel="Connectors"
      uitleg="Bronnen buiten de wettekst die Lex mag raadplegen en citeren, elk met een eigen vindplaats. Een bron is geen wettekst: Lex zegt wat de wet zegt alleen op grond van de bepaling zelf."
      segment="lex"
      onSegment={() => {}}
      tellers={{ lex: rijen.length }}
      zoek={lijst.zoek}
      onZoek={lijst.setZoek}
      zoekLabel="Zoeken in de connectors"
      groepen={[{ kop: "Bronnen naast de wet", rijen, leeg: "Er zijn nog geen connectors." }]}
      boven={beheerder && tfaNodig ? (
        <Melding type="waarschuwing" titel="Koppel eerst tweestapsverificatie">
          <p className="mb-2 text-sm">Aan- en uitzetten gaat pas als er een authenticator-app aan je account hangt.</p>
          <Button size="sm" variant="secondary" onClick={() => kiesInstellingenTab("beveiliging")}>Naar Beveiliging</Button>
        </Melding>
      ) : undefined}
      laden={!catalogus.data && !catalogus.fout && (beheerder ? beheer === null : aan === null) && !fout}
      fout={fout ?? (rijen.length === 0 ? catalogus.fout : null)}
      detail={open ? <ConnectorDetail id={open} alle={catalogus.data?.onderdelen ?? []} beheer={beheer}
        mag={beheerder && !tfaNodig} onWissel={wissel} bezig={bezig} onTerug={() => lijst.open(null)} /> : undefined}
    />
  );
}

function ConnectorDetail({ id, alle, beheer, mag, onWissel, bezig, onTerug }: {
  id: string;
  alle: Onderdeel[];
  beheer: Connector[] | null;
  mag: boolean;
  onWissel: (c: Connector) => void;
  bezig: string | null;
  onTerug: () => void;
}) {
  const { o, fout } = useOnderdeel(id);
  const c = beheer?.find((x) => x.naam === naamVan(id));
  const [audit, setAudit] = useState<ConnectorAuditRegel[] | null>(null);
  useEffect(() => {
    if (!mag) return;
    let weg = false;
    connectorAudit(naamVan(id)).then((a) => { if (!weg) setAudit(a); }).catch(() => { if (!weg) setAudit([]); });
    return () => { weg = true; };
  }, [id, mag, c?.aan]);
  const agents = alle.filter((a) => a.soort === "agentprofiel" && a.hangt_af_van.includes(id));
  const i = o?.inhoud ?? {};
  const velden = (["dekt", "rol_in_antwoord", "levert", "niet_in_tekst"] as const).filter((k) => tekst(i[k]));
  return (
    <AanpassingDetail terug="Connectors" onTerug={onTerug} laden={!o && !c} fout={o || c ? null : fout}
      titel={o?.label ?? c?.label} sub={o?.doel ?? c?.beschrijving}
      status={c ? <StatusLabel toon={c.aan ? "groen" : "neutraal"}>{c.aan ? "Aan" : "Uit"}</StatusLabel> : undefined}
      acties={c && mag ? (
        <Button size="sm" variant={c.aan ? "secondary" : "primary"} disabled={bezig === c.naam} onClick={() => onWissel(c)}>
          {bezig === c.naam ? "Bezig…" : c.aan ? "Uitzetten" : "Aanzetten"}</Button>
      ) : undefined}>
      <div className="space-y-4">
        {velden.length > 0 && (
          <Kaart titel="Wat deze bron dekt" data-blok="dekt">
            <Regels className="text-sm">
              {velden.map((k) => (
                <Regel key={k} naam={{ dekt: "Dekt", rol_in_antwoord: "In een antwoord", levert: "Levert", niet_in_tekst: "Niet in de tekst" }[k]}>
                  {tekst(i[k])}</Regel>
              ))}
            </Regels>
          </Kaart>
        )}
        <Kaart titel="Gebruikt door" telling={agents.length} data-blok="gebruikt-door">
          {agents.length ? (
            <ul className="space-y-1 text-sm">{agents.map((a) => (
              <li key={a.id}><button type="button" onClick={() => kiesInstellingenTab("agents", { onderdeel: a.id })}
                className="focus-ring rounded text-lint hover:underline">{a.label}</button></li>
            ))}</ul>
          ) : <Leeg>Geen agent gebruikt deze bron.</Leeg>}
        </Kaart>
        {mag && (
          <Kaart titel="Audit" data-blok="audit">
            {audit === null ? <Skeleton className="h-8 w-full" /> : (
              <ul className="space-y-0.5 text-xs text-muted" aria-label={`Audit van ${o?.label ?? c?.label ?? naamVan(id)}`}>
                {audit.length === 0 ? <li>Nog geen wijzigingen.</li> : audit.map((r, n) => (
                  <li key={n}>{datumTijd(r.tijdstip)}: {r.actie === "aan" ? "aangezet" : "uitgezet"} door {r.door}</li>
                ))}
              </ul>
            )}
          </Kaart>
        )}
        {o && <HerkomstKaart o={o} />}
      </div>
    </AanpassingDetail>
  );
}
