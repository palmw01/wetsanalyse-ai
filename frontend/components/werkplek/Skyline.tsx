/**
 * Een gestileerd stadssilhouet voor de werkplekheader: torens, een koepel en een zaal met puntgevel.
 * Eigen tekening, geen beeld of beeldmerk van derden. Puur decoratief (`aria-hidden`); de kleur komt
 * van `currentColor`, de diepte van twee lagen met elk een eigen dekking.
 */
export function Skyline({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 560 140"
      preserveAspectRatio="xMaxYMax slice"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {/* Achterste laag: hoge, slanke kantoortorens. */}
      <g fill="currentColor" fillOpacity="0.10">
        <rect x="40" y="58" width="26" height="82" />
        <rect x="72" y="40" width="20" height="100" />
        <rect x="330" y="30" width="24" height="110" />
        <rect x="360" y="52" width="30" height="88" />
        <rect x="470" y="44" width="22" height="96" />
        <rect x="498" y="66" width="34" height="74" />
        <path d="M150 140V50l14-14 14 14v90z" />
      </g>
      {/* Voorste laag: de zaal met puntgevel en torentjes, de koepeltoren en lage bebouwing. */}
      <g fill="currentColor" fillOpacity="0.18">
        <rect x="0" y="128" width="560" height="12" fillOpacity="0.6" />
        {/* zaal met puntgevel, geflankeerd door twee ronde torentjes */}
        <path d="M200 140V96l34-26 34 26v44z" />
        <rect x="190" y="88" width="10" height="52" />
        <path d="M190 88l5-10 5 10z" />
        <rect x="268" y="88" width="10" height="52" />
        <path d="M268 88l5-10 5 10z" />
        {/* koepeltoren */}
        <rect x="286" y="62" width="34" height="78" />
        <path d="M286 62a17 17 0 0 1 34 0z" />
        <rect x="301" y="34" width="4" height="12" />
        <rect x="294" y="46" width="18" height="2" />
        {/* lage bebouwing */}
        <rect x="100" y="96" width="44" height="44" />
        <rect x="400" y="90" width="52" height="50" />
        <path d="M400 90l26-14 26 14z" />
        <rect x="120" y="70" width="6" height="26" />
      </g>
    </svg>
  );
}
