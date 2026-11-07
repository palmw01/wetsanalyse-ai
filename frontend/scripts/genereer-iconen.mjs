// Maakt alle iconen van Lex uit één bron: merk/lex-merk.svg.
//
//   npm run iconen
//
// Uitvoer (Next.js App Router-conventies; de <link>-tags komen vanzelf, met een cache-hash):
//   app/icon.svg          – browsertab, met een eigen donkere stand (prefers-color-scheme)
//   app/favicon.ico       – 16, 32 en 48 px (PNG in ICO), voor oude browsers en /favicon.ico
//   app/apple-icon.png    – 180 px, opaak en tot de rand (iOS rondt zelf af)
//   public/icons/icon-192.png, icon-512.png – het manifest (purpose "any")
//   public/icons/icon-maskable-512.png      – het manifest (purpose "maskable"), merk binnen de veilige zone
//
// Deterministisch: opnieuw draaien geeft dezelfde bytes. Wijzig de bron, niet de uitvoer.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const bron = readFileSync(join(root, "merk/lex-merk.svg"), "utf8").replace(/<!--[\s\S]*?-->\s*/g, "");

/** Het vlak tot de rand, zonder afgeronde hoeken: voor apple-icon en maskable. */
const totDeRand = (svg) => svg.replace(/ rx="[^"]*"/, "");

/** Vorm en markering verkleind rond het midden; het vlak blijft vol. Voor de veilige zone van maskable. */
function verkleind(svg, schaal) {
  const start = svg.indexOf('<g class="vorm"');
  const eind = svg.lastIndexOf("</svg>");
  return `${svg.slice(0, start)}<g transform="translate(16 16) scale(${schaal}) translate(-16 -16)">${svg.slice(start, eind)}</g></svg>`;
}

/** De favicon-SVG: op een donkere tab vervalt het vlak en worden de regels licht; het geel blijft. */
function metDonkereStand(svg) {
  const stijl = "<style>@media (prefers-color-scheme:dark){.vlak{fill:none}.vorm{fill:#E8EFF7}}</style>";
  return svg.replace(/(<svg[^>]*>)/, `$1${stijl}`).replace(/>\s+</g, "><").trim() + "\n";
}

async function png(svg, px) {
  return sharp(Buffer.from(svg), { density: 72 * (px / 32) })
    .resize(px, px)
    .png({ compressionLevel: 9, palette: false })
    .toBuffer();
}

/** Opaak: zonder alfakanaal, zodat iOS er geen zwarte rand omheen zet. */
async function opaakPng(svg, px) {
  return sharp(Buffer.from(svg), { density: 72 * (px / 32) })
    .resize(px, px)
    .flatten({ background: "#154273" })
    .removeAlpha()
    .png({ compressionLevel: 9, palette: false })
    .toBuffer();
}

/** ICO met PNG-inhoud (Vista en later, alle huidige browsers). */
function ico(beelden) {
  const kop = Buffer.alloc(6 + 16 * beelden.length);
  kop.writeUInt16LE(0, 0);
  kop.writeUInt16LE(1, 2);
  kop.writeUInt16LE(beelden.length, 4);
  let offset = kop.length;
  beelden.forEach(({ px, data }, i) => {
    const o = 6 + 16 * i;
    kop.writeUInt8(px >= 256 ? 0 : px, o);
    kop.writeUInt8(px >= 256 ? 0 : px, o + 1);
    kop.writeUInt8(0, o + 2);
    kop.writeUInt8(0, o + 3);
    kop.writeUInt16LE(1, o + 4);
    kop.writeUInt16LE(32, o + 6);
    kop.writeUInt32LE(data.length, o + 8);
    kop.writeUInt32LE(offset, o + 12);
    offset += data.length;
  });
  return Buffer.concat([kop, ...beelden.map((b) => b.data)]);
}

const schrijf = (pad, inhoud) => {
  writeFileSync(join(root, pad), inhoud);
  console.log(`  ${pad}`);
};

console.log("Iconen van Lex uit merk/lex-merk.svg:");
schrijf("app/icon.svg", metDonkereStand(bron));
schrijf(
  "app/favicon.ico",
  ico(await Promise.all([16, 32, 48].map(async (px) => ({ px, data: await png(bron, px) })))),
);
schrijf("app/apple-icon.png", await opaakPng(totDeRand(bron), 180));
schrijf("public/icons/icon-192.png", await png(bron, 192));
schrijf("public/icons/icon-512.png", await png(bron, 512));
// Veilige zone: een cirkel met een diameter van 80 % van het canvas. De inhoud (6..26 op 32) heeft een
// halve diagonaal van 14,1; op 0,8 wordt dat 11,3, binnen de straal van 12,8.
schrijf("public/icons/icon-maskable-512.png", await opaakPng(verkleind(totDeRand(bron), 0.8), 512));
