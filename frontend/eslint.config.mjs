// Flat ESLint-config (ESLint 9). Next 16 verwijdert `next lint`; we draaien de ESLint-CLI
// direct. `eslint-config-next/core-web-vitals` levert vanaf v16 een flat-config-array
// (voorheen `extends: "next/core-web-vitals"` in .eslintrc.json).
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";

const config = [
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] },
  ...nextCoreWebVitals,
  {
    rules: {
      // Nieuw in de Next 16-config (react-hooks-plugin). Vlagt het gangbare, door React
      // toegestane patroon "setState binnen een sync-/fetch-effect" (loading-flags,
      // index-resets) dat onder Next 15 groen was. Stond eerst op `warn` zodat de bump
      // gedrag-neutraal bleef; inmiddels is elk van de tien voorkomens beoordeeld en voorzien
      // van een eigen `eslint-disable-next-line` met motivatie, dus `warn` ving niets meer.
      // Op `error` moet een níeuw geval eerst worden bekeken in plaats van in de ruis te
      // verdwijnen; de bestaande disables blijven gewoon werken.
      "react-hooks/set-state-in-effect": "error",
    },
  },
  {
    // Config-modules exporteren bewust een anonieme default (framework-conventie).
    files: ["*.config.mjs", "*.config.js"],
    rules: { "import/no-anonymous-default-export": "off" },
  },
];

export default config;
