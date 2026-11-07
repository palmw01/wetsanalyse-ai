"use client";

import { BewerkVoet } from "@/components/ui/Bewerkbaar";
import { useState } from "react";
import { Field, Input, Select } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import { FormRaster, SettingGroup } from "@/components/ui/SettingRow";
import { isApiError, saveProfile } from "@/lib/api";
import type { LlmProfileIn, LlmProfileOut } from "@/lib/types";

interface Props {
  /** Bestaand profiel bij bewerken; null bij nieuw. */
  profile: LlmProfileOut | null;
  onDone: () => void;
  onCancel: () => void;
}

const PROVIDERS = ["azure_ai", "azure", "openai", "anthropic", "bedrock"];

export function ProfileEditor({ profile, onDone, onCancel }: Props) {
  const nieuw = profile === null;
  const [naam, setNaam] = useState(profile?.name ?? "");
  const [provider, setProvider] = useState(profile?.provider ?? "azure_ai");
  const [model, setModel] = useState(profile?.model ?? "");
  const [apiBase, setApiBase] = useState(profile?.api_base ?? "");
  const [apiVersion, setApiVersion] = useState(profile?.api_version ?? "");
  const [temperature, setTemperature] = useState(String(profile?.temperature ?? 0));
  const [outputStrategy, setOutputStrategy] = useState(profile?.output_strategy ?? "prompt_and_parse");
  const [apiKey, setApiKey] = useState("");
  const [bezig, setBezig] = useState(false);
  const [fout, setFout] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFout(null);
    if (!naam.trim()) return setFout("Naam is verplicht.");
    if (!model.trim()) return setFout("Model is verplicht.");

    const body: LlmProfileIn = {
      provider,
      model: model.trim(),
      api_base: apiBase.trim(),
      api_version: apiVersion.trim() || null,
      output_strategy: outputStrategy,
      temperature: Number(temperature) || 0,
    };
    if (apiKey.trim()) body.api_key = apiKey.trim();

    setBezig(true);
    try {
      await saveProfile(naam.trim(), body);
      onDone();
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
      setBezig(false);
    }
  }

  return (
    <SettingGroup titel={nieuw ? "Nieuw profiel" : `Profiel bewerken – ${profile?.name}`}>
      <form onSubmit={onSubmit} className="space-y-5">
        <FormRaster>
          <Field label="Naam" required hint={nieuw ? "uniek, bv. azure-sonnet" : "vast"}>
            <Input value={naam} onChange={(e) => setNaam(e.target.value)} disabled={!nieuw} placeholder="azure-sonnet" autoComplete="off" />
          </Field>
          <Field label="Provider" required>
            <Select value={provider} onChange={(e) => setProvider(e.target.value)}>
              {PROVIDERS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </Select>
          </Field>
          <Field label="Model" required hint="bv. claude-sonnet-4-6">
            <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="claude-sonnet-4-6" autoComplete="off" />
          </Field>
          <Field label="API-base" hint="endpoint-URL">
            <Input value={apiBase} onChange={(e) => setApiBase(e.target.value)} placeholder="https://…services.ai.azure.com" autoComplete="off" />
          </Field>
          <Field label="API-version" hint="alleen Azure OpenAI">
            <Input value={apiVersion} onChange={(e) => setApiVersion(e.target.value)} placeholder="2024-10-21" autoComplete="off" />
          </Field>
          <Field label="Temperatuur" hint="0 = deterministisch">
            <Input type="number" step="0.1" min="0" max="2" value={temperature} onChange={(e) => setTemperature(e.target.value)} />
          </Field>
          <Field label="Output-strategie">
            <Select value={outputStrategy} onChange={(e) => setOutputStrategy(e.target.value)}>
              <option value="prompt_and_parse">prompt_and_parse</option>
              <option value="json_object">json_object</option>
            </Select>
          </Field>
          <Field
            label="API-key"
            hint={profile?.api_key_set ? "ingesteld – leeg laten = ongewijzigd" : "write-only"}
          >
            <Input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={profile?.api_key_set ? "••••••••" : "sk-…"} autoComplete="new-password" />
          </Field>
        </FormRaster>

        {fout && <Melding type="fout">{fout}</Melding>}

        {/* Dezelfde voet als elk bewerkveld in Lex (4 nov 2026): rechts Annuleren · Opslaan. */}
        <BewerkVoet submit onAnnuleer={onCancel} bezig={bezig} gewijzigd />
      </form>
    </SettingGroup>
  );
}
