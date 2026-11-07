// Het IP-adres van de browser achter een inlogpoging, voor de inlogrem van de api (`api/app/ratelimit.py`). De api
// remt missers per (client-IP, userid), zodat de missers van een aanvaller niet de echte gebruiker buitensluiten.
// De BFF zet het in `X-Client-IP` op de aanroep van `/v1/auth/verify` (`lib/server.ts`); de api gelooft die header
// alleen van de frontend-client.
//
// Welk adres te vertrouwen is: de frontend staat direct achter de ingress van Azure Container Apps. Die vult
// `X-Forwarded-For` aan met het adres van de verbinding die hij ontving en laat staan wat de client zelf meestuurde
// (learn.microsoft.com/azure/container-apps/ingress-overview, §HTTP headers: alleen het meest rechtse adres komt
// van Container Apps, de rest moet je zelf valideren). Alleen het **laatste** element komt dus van de ingress; alles
// links ervan kan de browser hebben verzonnen. Zonder ingress (lokaal) vult de Next-server `X-Forwarded-For` met het
// socketadres als hij ontbreekt, en dan is het laatste element dat adres.
//
// Komt er ooit een proxy vóór de ingress (Front Door, Application Gateway), dan is het laatste element het adres van
// die proxy en remt de api iedereen achter die proxy samen: tel dan hier het aantal vertrouwde hops mee.

/** Het laatste element van `X-Forwarded-For`, zonder poort, als het een IP-adres lijkt; anders null. De api
 *  valideert het opnieuw. */
export function clientIpUitHeaders(headers: Pick<Headers, "get">): string | null {
  const xff = headers.get("x-forwarded-for");
  if (!xff) return null;
  let laatste = (xff.split(",").pop() ?? "").trim();
  // Sommige proxies zetten er een poort achter: "[2001:db8::1]:443" of "192.0.2.1:443".
  const metHaken = /^\[([^\]]+)\](?::\d+)?$/.exec(laatste);
  if (metHaken) laatste = metHaken[1];
  else if (/^[\d.]+:\d+$/.test(laatste)) laatste = laatste.slice(0, laatste.lastIndexOf(":"));
  // Ruwe vormtoets: IPv4 of IPv6 (hex, punten, dubbele punten), geen zone of andere tekens.
  if (!laatste || laatste.length > 45 || !/^[0-9a-fA-F.:]+$/.test(laatste)) return null;
  return laatste;
}
