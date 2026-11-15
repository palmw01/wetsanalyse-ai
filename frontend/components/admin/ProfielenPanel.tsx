"use client";

import { useCallback, useEffect, useState } from "react";
import { AanpassingLijst, VoegToeMenu } from "@/components/instellingen/AanpassingLijst";
import { MeerMenu, MenuKnop, MenuVerwijder } from "@/components/ui/MeerMenu";
import { Melding } from "@/components/ui/Melding";
import { deleteProfile, haalModelkeuzesBeheer, isApiError, listProfiles, setDefaultProfile, testProfile } from "@/lib/api";
import { gebruiktDoor, type Overzicht } from "@/lib/modelkeuzes";
import type { LlmProfileOut, TestResult } from "@/lib/types";
import { ProfileEditor } from "./ProfileEditor";
import { StatusLabel } from "@/components/ui/Lijst";

type EditState = { open: false } | { open: true; profile: LlmProfileOut | null };

export function ProfielenPanel() {
  const [profielen, setProfielen] = useState<LlmProfileOut[] | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [edit, setEdit] = useState<EditState>({ open: false });
  const [tests, setTests] = useState<Record<string, TestResult | "bezig">>({});
  const [zoek, setZoek] = useState("");
  // Waar elk profiel gekozen is (de modelkeuzes per agent en stap). Stil falend: het is een toelichting.
  const [keuzes, setKeuzes] = useState<Overzicht | null>(null);

  const laad = useCallback(async () => {
    setFout(null);
    try {
      setProfielen(await listProfiles());
      setKeuzes(await haalModelkeuzesBeheer().catch(() => null));
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
      setProfielen([]);
    }
  }, []);

  useEffect(() => {
    laad();
  }, [laad]);

  async function onTest(name: string) {
    setTests((t) => ({ ...t, [name]: "bezig" }));
    try {
      const res = await testProfile(name);
      setTests((t) => ({ ...t, [name]: res }));
    } catch (e) {
      setTests((t) => ({
        ...t,
        [name]: { ok: false, model: "", tokens_in: 0, tokens_out: 0, detail: isApiError(e) ? e.detail : (e as Error).message },
      }));
    }
  }

  async function onDefault(name: string) {
    try {
      await setDefaultProfile(name);
      await laad();
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
    }
  }

  async function onDelete(name: string) {
    try {
      await deleteProfile(name);
      await laad();
    } catch (e) {
      // Gekozen voor een agent of stap (409 `in_gebruik`): noem ze bij naam, niet bij hun sleutel.
      const sleutels = isApiError(e) && Array.isArray(e.data?.gebruikt_door) ? (e.data.gebruikt_door as string[]) : null;
      if (sleutels && keuzes) {
        const label = Object.fromEntries(keuzes.keuzes.map((k) => [k.sleutel, k.label]));
        setFout(`"${name}" is gekozen voor ${sleutels.map((s) => label[s] ?? s).join(", ")}. Zet die eerst bij Agents op een ander profiel of op Standaard.`);
        return;
      }
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
    }
  }

  if (edit.open) {
    return (
      <ProfileEditor
        profile={edit.profile}
        onCancel={() => setEdit({ open: false })}
        onDone={() => {
          setEdit({ open: false });
          laad();
        }}
      />
    );
  }

  // De tab Modellen in Instellingen › Aanpassingen (plan instellingen-aanpassingen): dezelfde lijst als Methodes, Agents
  // en Connectors. Een rij opent de editor; *Test verbinding*, *Als standaard* en *Verwijderen* staan in het menu ⋯, de
  // uitkomst van een test onder de rij.
  const rijen = (profielen ?? []).map((p) => {
    const test = tests[p.name];
    return {
      id: p.name, naam: p.name, titel: p.name, zoektekst: `${p.name} ${p.provider} ${p.model}`,
      onOpen: () => setEdit({ open: true, profile: p }),
      sub: [p.provider, p.model || "geen model", keuzes && gebruiktDoor(keuzes, p.name).length
        ? `gekozen voor ${gebruiktDoor(keuzes, p.name).join(", ")}` : ""].filter(Boolean).join(" · "),
      status: <>
        {p.is_default && <StatusLabel toon="lint">standaard</StatusLabel>}
        <StatusLabel toon={p.api_key_set ? "groen" : "geel"}>{p.api_key_set ? "API-key ingesteld" : "Geen API-key"}</StatusLabel>
      </>,
      eind: (
        <MeerMenu label={`Acties voor ${p.name}`}>
          {(sluit) => <>
            <MenuKnop onClick={() => { sluit(); void onTest(p.name); }}>Test verbinding</MenuKnop>
            {!p.is_default && <MenuKnop onClick={() => { sluit(); void onDefault(p.name); }}>Als standaard</MenuKnop>}
            {!p.is_default && <MenuVerwijder onBevestig={() => { sluit(); return onDelete(p.name); }} vraag={`"${p.name}" verwijderen?`} />}
          </>}
        </MeerMenu>
      ),
      onder: test === "bezig" ? <p className="px-4 pb-3 text-xs text-muted">Verbinding testen…</p> : test ? (
        <div className="px-4 pb-3">
          <Melding type={test.ok ? "bevestiging" : "fout"} compact className="text-xs">
            {test.ok
              ? `Verbinding OK – model ${test.model} (${test.tokens_in + test.tokens_out} tokens).`
              : `Test mislukt: ${test.detail}`}
          </Melding>
        </div>
      ) : undefined,
      data: { "data-profiel": p.name },
    };
  });

  return (
    <AanpassingLijst
      titel="Modellen"
      uitleg="De modelprofielen: welk model, bij welke aanbieder. De API-key wordt versleuteld bewaard en nooit getoond."
      voegToe={<VoegToeMenu keuzes={[{ label: "Nieuw profiel", data: "nieuw", onKies: () => setEdit({ open: true, profile: null }) }]} />}
      segment="lex"
      onSegment={() => {}}
      tellers={{ lex: rijen.length }}
      zoek={zoek}
      onZoek={setZoek}
      zoekLabel="Zoeken in de modellen"
      groepen={[{ kop: "Modelprofielen", rijen, leeg: "Nog geen profielen." }]}
      laden={profielen === null}
      fout={fout}
    />
  );
}
