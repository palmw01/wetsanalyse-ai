# Juridisch relevante feiten en waarden

Grondslag: [bronnen](bronnen.md) — J01 H4 en H5, JP02.

## Inhoud

- Wat een juridisch relevant feit is
- Type en instantie
- Bepalend en bepaald
- Waarde
- Van feit naar gegevensmodel
- Controlelijst
- Methodetekst voor Lex

## Wat een juridisch relevant feit is

Een juridisch relevant feit is een feit dat (J01, H4):
1. voorkomt in een voorwaarde op een rechtssubject, rechtsbetrekking of rechtsfeit;
2. een onderdeel is van een rechtsobject; en/of
3. invoer of uitvoer is van een afleidingsregel.

Het verschil met een variabele is de samenhang. Een variabele is een plek voor een waarde (*jaarinkomen*). Een
juridisch relevant feit zegt **van wie en wanneer**: *de natuurlijk persoon met burgerservicenummer 123456789 heeft
een jaarinkomen van € 35.000 in het kalenderjaar 2023* (voorbeeld uit J01, H4). Een feit bestaat niet zomaar: het dient
een voorwaarde, een object of een afleidingsregel. Vind je er geen, dan is het waarschijnlijk geen juridisch relevant
feit.

## Type en instantie

Schrijf het type als zin met de onderdelen tussen punthaken:

> natuurlijke persoon met BSN `<BSN>` heeft jaarinkomen `<jaarinkomen>` in kalenderjaar `<kalenderjaar>`

De instantie vult de onderdelen in. Een feittype heeft dezelfde vorm in de wet en in de uitvoering; zo praten
juristen en modelleurs over hetzelfde.

## Bepalend en bepaald

Zeg welke onderdelen het feit identificeren (**bepalend**) en welke de uitkomst zijn (**bepaald**). In het
voorbeeld bepalen BSN en kalenderjaar samen het jaarinkomen. Dat is de opmaat naar een sleutel in het gegevensmodel.

## Waarde

Het JRM voegt parameterwaarde en variabelewaarde samen tot **waarde**: een in de wet opgenomen waarde, gekoppeld aan
een (min of meer) constante of aan een variabele (J01, H5). In Lex blijven de JAS-paren *variabele en variabelewaarde*
en *parameter en parameterwaarde* het label; de toelichting zegt welke helft je bedoelt.

## Van feit naar gegevensmodel

De juridisch relevante feiten samen zijn de opmaat naar het gegevensdeel van het kennismodel. In Fact Based Modelling
worden ze feittypen; in een ER-model attribuuttypen, associaties of attributen van associatieklassen. Modelleer je
direct in ER, let dan zelf op de samenhang die het feittype uitdrukt.

## Controlelijst

```
Feittype – controle
- [ ] Waar dient het feit: welke voorwaarde, welk object, welke afleidingsregel (met bepaling)?
- [ ] Type als zin met <onderdelen>; instantie als ingevulde zin
- [ ] Bepalende en bepaalde onderdelen benoemd
- [ ] Elk onderdeel is een JAS-element in de markeringen (rechtssubject, variabele, tijdsaanduiding, …)
- [ ] Een feit dat in een voorwaarde staat en door een afleidingsregel wordt berekend: die keten benoemd
```

## Methodetekst voor Lex

Deze sectie is nog aan geen rol gekoppeld (JP04).

<!-- methode:jrm-relevant-feit:begin -->
Een juridisch relevant feit verbindt een waarde met de elementen waar zij bij hoort, zoals een persoon en een kalenderjaar; het staat in een voorwaarde, is een onderdeel van een rechtsobject, of is invoer of uitvoer van een afleidingsregel. Beschrijf het waar het helpt als feittype met onderdelen tussen punthaken, en zeg welke onderdelen het feit bepalen en welk onderdeel bepaald wordt. Een losse variabele zonder die samenhang is onvoldoende. Noem de bepaling die het feit nodig maakt. Een waarde is een in de wet opgenomen waarde bij een constante of een variabele; het JAS-label blijft het paar variabele of parameter met waarde.
<!-- methode:jrm-relevant-feit:end -->
