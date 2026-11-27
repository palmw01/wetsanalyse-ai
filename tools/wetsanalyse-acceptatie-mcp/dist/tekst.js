/** Tekstbewerkingen zonder kwadratische reguliere expressie (SonarQube S8786). Elk geeft precies het resultaat van de
 *  expressie die het vervangt, in één doorgang. */
/** Als `s.replace(/<[^>]*>/g, "")`. Na een `<` zonder `>` verderop is er geen match meer: elke latere `<` mist die ook. */
export function zonderTags(s) {
    let uit = "";
    let i = 0;
    while (i < s.length) {
        const open = s.indexOf("<", i);
        if (open < 0)
            break;
        const dicht = s.indexOf(">", open + 1);
        if (dicht < 0)
            break;
        uit += s.slice(i, open);
        i = dicht + 1;
    }
    return uit + s.slice(i);
}
/** Als `s.replace(/\/+$/, "")`. */
export function zonderSlotslash(s) {
    let eind = s.length;
    while (eind > 0 && s[eind - 1] === "/")
        eind--;
    return s.slice(0, eind);
}
const WOORD = /[\w.-]/;
const WAARDE = /[\w.%-]/;
/** Als `s.replace(/[\w.-]*:[\w.%-]*\/g, vervanging)`: elk voorvoegsel met naam (`bwb:Artikel`, `urn:…`) vervangen.
 *  Een reeks woordtekens zonder `:` erachter levert vanaf geen enkele positie erin een match op, dus die wordt in één keer
 *  overgeslagen in plaats van vanaf elke positie opnieuw gelezen. */
export function zonderVoorvoegselnamen(s, vervanging) {
    let uit = "";
    let i = 0;
    while (i < s.length) {
        let j = i;
        while (j < s.length && WOORD.test(s[j]))
            j++;
        if (s[j] === ":") {
            let k = j + 1;
            while (k < s.length && WAARDE.test(s[k]))
                k++;
            uit += vervanging;
            i = k;
        }
        else if (j > i) {
            uit += s.slice(i, j);
            i = j;
        }
        else {
            uit += s[i];
            i++;
        }
    }
    return uit;
}
