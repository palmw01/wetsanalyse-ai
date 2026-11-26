"use client";

import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";

import { AanpassingLijst, useLijstStand } from "@/components/instellingen/AanpassingLijst";
import { Button } from "@/components/ui/Button";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { foutTekst, getAccount, haalPlugins, listPlugins, zetPlugin, type PluginBeheer } from "@/lib/api";
import { datumTijd } from "@/lib/datum";
import { kiesInstellingenTab } from "@/lib/instellingenVenster";

/** Instellingen › Aanpassingen › Plugins (plan contenttoets, C4): een werkwijze naast de wetsanalyse, zoals de
 *  contenttoets, met een eigen commando. Zoals in Claude Code staan plugins apart van de connectors (de bronnen buiten de
 *  wettekst). Welke er bestaan staat in de code; een beheerder met 2FA biedt er een aan (elke wijziging staat in de audit),
 *  in het gesprek zet je hem aan of uit in het menu boven het invoerveld. Een analist ziet wat aangeboden is, zonder knop.
 *  Een rij opent de skill onder Methodes. */
export function PluginsPanel() {
  const { data: sessie } = useSession();
  const beheerder = sessie?.user?.role === "beheerder";
  const lijst = useLijstStand(false);
  const [beheer, setBeheer] = useState<PluginBeheer[] | null>(null);
  const [aangeboden, setAangeboden] = useState<PluginBeheer[] | null>(null);
  const [tfaNodig, setTfaNodig] = useState(false);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState<string | null>(null);

  const laad = useCallback(async () => {
    setFout(null);
    try {
      if (beheerder) {
        const [account, alle] = await Promise.all([getAccount(), listPlugins()]);
        setTfaNodig(account.tfa_nodig);
        setBeheer(alle);
      } else {
        const plugins = await haalPlugins();
        setAangeboden(plugins.map((p) => ({ ...p, aan: true, door: "", bijgewerkt: "" })));
      }
    } catch (e) {
      setFout(foutTekst(e, "De plugins konden niet worden geladen."));
    }
  }, [beheerder]);

  useEffect(() => {
    // Data-load bij mount: setState gebeurt async ná de fetch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (sessie) void laad();
  }, [laad, sessie]);

  async function wissel(p: PluginBeheer) {
    setBezig(p.naam);
    setFout(null);
    try {
      const nieuw = await zetPlugin(p.naam, !p.aan);
      setBeheer((oud) => oud?.map((x) => (x.naam === nieuw.naam ? nieuw : x)) ?? null);
    } catch (e) {
      setFout(foutTekst(e, "De plugin kon niet worden omgezet."));
    } finally {
      setBezig(null);
    }
  }

  const rijen = (beheer ?? aangeboden ?? []).map((p) => ({
    id: `plugin/${p.naam}`, naam: p.label, titel: p.label, zoektekst: `${p.label} ${p.beschrijving} ${p.commando} plugin`,
    onOpen: () => kiesInstellingenTab("methodes", { onderdeel: `methode/${p.naam}` }),
    sub: [p.beschrijving, `Commando /${p.commando}`,
      p.door && `${p.aan ? "Aangeboden" : "Niet aangeboden"} door ${p.door}${p.bijgewerkt ? `, ${datumTijd(p.bijgewerkt)}` : ""}`]
      .filter(Boolean).join(" · "),
    status: <StatusLabel toon={p.aan ? "groen" : "neutraal"}>{p.aan ? "Aangeboden" : "Uit"}</StatusLabel>,
    eind: beheer && !tfaNodig ? (
      <Button size="sm" variant={p.aan ? "secondary" : "primary"} disabled={bezig === p.naam} onClick={() => wissel(p)}>
        {bezig === p.naam ? "Bezig…" : p.aan ? "Uitzetten" : "Aanbieden"}</Button>
    ) : undefined,
    data: { "data-plugin-rij": p.naam },
  }));

  return (
    <AanpassingLijst
      titel="Plugins"
      uitleg="Werkwijzen naast de wetsanalyse, elk met een eigen commando, zoals /contenttoets. Een beheerder biedt een plugin aan; in het gesprek zet je hem aan of uit in het menu boven het invoerveld."
      segment="lex"
      onSegment={() => {}}
      tellers={{ lex: rijen.length }}
      zoek={lijst.zoek}
      onZoek={lijst.setZoek}
      zoekLabel="Zoeken in de plugins"
      groepen={[{ kop: "Plugins", rijen, leeg: beheerder ? "Er zijn nog geen plugins." : "Er is nog geen plugin aangeboden." }]}
      boven={beheerder && tfaNodig ? (
        <Melding type="waarschuwing" titel="Koppel eerst tweestapsverificatie">
          <p className="mb-2 text-sm">Aanbieden en uitzetten gaat pas als er een authenticator-app aan je account hangt.</p>
          <Button size="sm" variant="secondary" onClick={() => kiesInstellingenTab("beveiliging")}>Naar Beveiliging</Button>
        </Melding>
      ) : undefined}
      laden={(beheerder ? beheer === null : aangeboden === null) && !fout}
      fout={fout}
    />
  );
}
