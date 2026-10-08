/// <reference lib="webworker" />
/** Rekent de layout buiten de hoofdthread, zodat de werkplek bedienbaar blijft terwijl de hele
 *  kennisgraaf wordt gelegd. Eén verzoek per worker; `rekenaar.ts` maakt hem aan en ruimt hem op. */
import { berekenLayout } from "./layout";
import { naarReeksen, uitReeksen } from "./cache";
import type { LayoutBericht, LayoutVerzoek } from "./rekenaar";

const zend = (bericht: LayoutBericht, overdracht: Transferable[] = []) => self.postMessage(bericht, overdracht);

self.onmessage = (e: MessageEvent<LayoutVerzoek>) => {
  try {
    const { structuur, vast } = e.data;
    let laatst = -1;
    const pos = berekenLayout(structuur, {
      vast: vast ? uitReeksen(vast.ids, vast.xy) : undefined,
      // Hooguit honderd berichten: elke procent.
      opVoortgang: (f) => {
        const procent = Math.floor(f * 100);
        if (procent !== laatst) zend({ soort: "voortgang", fractie: f });
        laatst = procent;
      },
    });
    const { ids, xy } = naarReeksen(pos);
    zend({ soort: "klaar", ids, xy }, [xy.buffer]);
  } catch (fout) {
    zend({ soort: "fout", reden: fout instanceof Error ? fout.message : String(fout) });
  }
};
