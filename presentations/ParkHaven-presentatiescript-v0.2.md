# ParkHaven Studio — presentatiescript v0.2

## Dia 1: Introductie
ParkHaven Studio is een lokale ontwerpomgeving die een Rhino-model omzet in een begrijpelijke ontwerpbeoordeling. De app brengt Rhino, Grasshopper, modelbeelden, meetresultaten en rapportage samen in één begeleide route. De gebruiker importeert een ontwerp, plaatst het op de locatie, analyseert het en maakt een controleerbaar verslag. Eerst bekijken we die hoofdwerking; daarna zoomen we in op de technische opbouw.

## Dia 2: Waarom
Het huidige proces is vaak versnipperd. Geometrie staat in Rhino, berekeningen in Grasshopper, beelden worden handmatig gemaakt en conclusies belanden in losse documenten. Daardoor is moeilijk te herleiden welke uitkomst bij welke modelversie hoort. ParkHaven Studio verbindt die onderdelen, bewaart de bron en koppelt iedere analyse, afbeelding en conclusie aan dezelfde modelstatus. Zo wordt itereren overzichtelijker en beter uitlegbaar.

## Dia 3: Gebruikersworkflow
Voor de gebruiker zijn er vijf stappen. Eerst wordt een 3DM-bestand geïmporteerd. Daarna controleert de ontwerper positie, rotatie en modeleenheid met een snelle 3D-preview. Vervolgens start de lokale Rhino- en Grasshopper-analyse. Na afloop toont de app prestaties en vier vaste modelbeelden. Optioneel volgt begrensd AI-advies. Tot slot ontstaat een leesbaar rapport dat als PDF kan worden opgeslagen.

## Dia 4: Werkruimte
De centrale werkruimte is de 3D-viewer. Hier staat het ontwerp naast gevels, parkdoel, referentiegebouwen en de lokale luchtfoto. Lagen kunnen afzonderlijk aan en uit, en vaste camera's maken varianten vergelijkbaar. Ontwerpvolumes houden overal dezelfde kleuren: blauw, oranje en paars. Zo blijven Volume A, B en C herkenbaar in de viewer, de bewijsbeelden en het rapport.

## Dia 5: Resultaten
De app levert kerngetallen zoals bruto vloeroppervlak, zicht en indicatieve kosten. Daarnaast zijn er vergelijkende screenings voor zon, thermisch comfort en fundering; deze zijn geen definitief ingenieursadvies. Alles komt samen in een ontwerpverslag met modelbeelden, meetresultaten, aannames en eventuele ontwerpacties. Het resultaat is dus niet alleen een dashboard, maar een dossier dat de onderbouwing van een ontwerpkeuze zichtbaar maakt.

## Dia 6: Architectuur
Onder de interface werken zes onderdelen samen. Een Windows-programma met WebView2 toont de app. De lokale FastAPI-backend beheert projecten, runs en rapporten. Three.js verzorgt de 3D-viewer. Voor analyse opent de backend Rhino zichtbaar; een eigen plug-in laadt de Grasshopper-definitie en exporteert JSON-resultaten. Een optionele AI-provider ontvangt alleen begrensde tekst. Beelden blijven lokaal en het rapport wordt lokaal opgebouwd.

## Dia 7: Run-isolatie
Iedere analyse is technisch een geïsoleerde run. Het originele 3DM-bestand blijft ongewijzigd. Per run maakt de app een modelkopie, jobbestand, Grasshopper-definitie, weerbestand en datamap. Meetwaarden, scene en geometriesamenvatting worden atomair gepubliceerd. SHA-256-hashes koppelen bron, definitie, weerdata, resultaten en beelden. Daardoor kan de app verouderd of verwisseld bewijs weigeren en overschrijft een nieuwe analyse niet ongemerkt een eerder resultaat.

## Dia 8: Bewijs en AI
De bewijs- en AI-keten heeft een harde datagrens. De viewer maakt vier gestandaardiseerde beelden met bekende camera's en lagen. De backend bouwt daarnaast een compacte tekstbeschrijving van volumes en meetwaarden. Alleen die tekst mag naar een AI-endpoint; afbeeldingen en ruwe geometrie blijven lokaal. Het antwoord wordt gevalideerd op bekende volumes en meetwaarden. Verschuivingen zijn toegestaan als verkennende tests, maar zonder geverifieerde plot- of tunnelcontour gelden ze nooit als bewijs van haalbaarheid.

## Dia 9: Status en roadmap
De basisworkflow werkt nu van import tot PDF en is getest met het echte Parkhaven-model. De huidige versie ondersteunt projectopslag, plaatsing, Rhino- en Grasshopper-analyse, 3D-weergave, bewijsbeelden, begrensd AI-advies en rapportage. De volgende fase richt zich op betrouwbaarheid: geverifieerde locatiegrenzen, gekalibreerde normen, ondertekende distributie en tests op schone machines. De kern staat; v0.2 bereidt de app voor op bredere praktijktesten.
