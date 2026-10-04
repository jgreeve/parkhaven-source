# ParkHaven AI Work Guide

Compacte werkinstructie voor AI-modellen en ontwikkelaars. Doel: veilig verder
werken met zo weinig mogelijk tokens, bestandslezingen en herhaalde context.

## 1. Start hier

Lees standaard alleen deze bestanden, in deze volgorde:

1. Dit bestand.
2. [`progress.md`](progress.md), alleen **Current stage**, **Known limitations** en
   **Exact next tasks**. Zoek de koppen; lees niet automatisch het hele bestand.
3. [`../ParkHaven_Analyzer_App_v0.2/docs/plan.md`](../ParkHaven_Analyzer_App_v0.2/docs/plan.md),
   alleen sectie **0**, de relevante fase en **Revised implementation sequence**.
4. Daarna uitsluitend de bronbestanden die voor de concrete taak nodig zijn.

`progress.md` is de waarheid over wat aantoonbaar werkt. `plan.md` is de roadmap,
niet het bewijs dat iets al gebouwd is. Deze gids beschrijft hoe je efficiënt werkt.

## 2. Projectgrenzen

- Desktopimplementatie: `ParkHaven_App_v0.1/`.
- Geverifieerde analyser/referentie: `../ParkHaven_Analyzer_App_v0.2/`.
- Verander de analyser alleen als de taak dit expliciet vereist. De desktop gebruikt
  diens `ParkHaven_MVP.3dm`, GHX en lokaal gevendorde Three.js-assets.
- Platform: Windows 10/11; Rhino 8 met geldige licentie is vereist.
- UI en gebruikersmeldingen zijn Nederlands. Code en technische documentatie zijn
  overwegend Engels; volg het bestaande bestand.
- De originele geïmporteerde `.3dm` mag nooit stilzwijgend worden gewijzigd.
- Grasshopper blijft de autoriteit voor BVO, zicht en kosten.
- AI mag berekende waarden niet aanpassen of als zelf berekend presenteren.

## 3. Huidige staat in één alinea

De WPF/WebView2-desktop start een eigen, geauthenticeerde FastAPI-backend en kan
projecten importeren, eenheden/plaatsing opslaan, Rhino/Grasshopper automatisch
uitvoeren, resultaten rapporteren en model-grounded AI-advies aanvragen. Dora werkt
met expliciete coördinaatinterpretatie **Meters — 1 = 1 m**. Een read-only Three.js-
viewer toont `scene.json` van de nieuwste voltooide run met lagen, Z-up/meterraster,
afmetingen en cameracontroles. Een geisoleerde pre-analysepreview toont ook
visual-only geometrie en live numerieke/unit-conceptplaatsing zonder context te
verplaatsen. Een begrensde XY/Z-gizmo met lokaal oorsprong/centrumreferentie werkt;
stabiele design/visual-ID's en rungebonden geometriesamenvattingen zijn beschikbaar.
Vier gecontroleerde, gehashte real-scene captures zijn aan dezelfde run/metrics
gebonden. De AI-route vereist dit pakket en stuurt metrics, begrensde geometrie en
vier gelabelde beelden; teruggegeven metric-, view- en objectreferenties worden
gevalideerd. Geverifieerd noorden/plot/maaiveld en live Spark vision-acceptatie
ontbreken nog. De viewer toont daarnaast een gehashte lokale PDOK 2025-luchtfoto
onder de bestaande 3D-context; deze uitlijning is voorlopig en uitsluitend visueel.

Controleer altijd `progress.md` voor nieuwere informatie.

## 4. Volgende ontwikkelvolgorde

1. Live Spark-acceptatie met gebruikerscredentials en het exacte vision-model.
2. Oriëntatiecontrole met geverifieerde noord/plot/maaivelddata waar beschikbaar.

Conceptuele AI-renders zijn voorlopig uit scope. Echte captures van de bestaande
3D-scene blijven nodig voor AI-advies en rapportage.

## 5. Architectuurkaart

| Onderdeel | Belangrijkste bestanden |
|---|---|
| FastAPI/API | `app/main.py`, `app/session.py` |
| Projecten/plaatsing | `app/projects.py` |
| Runs/Rhino-proces | `app/workflow.py` |
| Diagnostiek | `app/diagnostics.py` |
| AI-client/TLS | `app/ai.py`, `app/ai_tls.py`, `config/ai-trust.json` |
| Rapport | `app/reports.py` |
| Web-UI | `app/static/index.html`, `app/static/app.js`, `app/static/styles.css` |
| 3D-viewer | `app/static/viewer.js`; scene-route in `app/main.py` |
| Luchtfotocontext | `app/site_context.py`, `site-context/manifest.json`, `docs/CONTEXT_PROVENANCE.md` |
| Desktophost | `desktop/ParkHaven.Desktop/` |
| Rhino-plug-in | `rhino-plugin/AnalysisJob.cs`, `ModelPreparation.cs`, `GrasshopperSolver.cs`, `ParkHavenPlugin.cs` |
| Python-tests | `tests/test_*.py` |
| Browser/native smoke | `tests/browser_workflow_smoke.py`, `desktop_*_smoke.py` |
| Live Rhino-verificatie | `scripts/verify_rhino_plugin.py`, `verify_rhino_import.py`, `verify_rhino_unit_equivalence.py` |

Zoek eerst op symbool, route, automation-ID of zichtbare tekst. Lees geen volledige
directory of groot bestand wanneer een gerichte zoekopdracht voldoende is.

## 6. Belangrijke contracten

### Project en run

- Project-ID en run-ID zijn UUID's; paden mogen de projectroot niet verlaten.
- Elke run heeft een eigen snapshot, GHX, `job.json` en `data/`.
- Een run wordt nooit hergebruikt of achteraf herschreven met nieuwe plaatsing.
- Actieve fasen: `launch_requested`, `runner_started`, `preparing_model`, `solving`.
- Terminale fasen: `completed`, `failed`, `cancelled`.

### Plaatsing en eenheden

- X/Y/Z zijn fysieke meters; rotatie is rond Z.
- `model_units` is `file`, `meters`, `millimeters` of `centimeters`.
- Eenheidscorrectie gebeurt alleen in de analyse-/previewkopie, vóór rotatie en
  translatie. Bron, preserved copy en project working copy blijven byte-identiek.
- Raad eenheden niet automatisch. Toon afwijkende schaal en laat de gebruiker kiezen.

### 3D-scene

`scene.json` contract:

```json
{"schema_version":1,"units":"meters","up_axis":"Z","layers":[
  {"name":"PH_DESIGN","vertices":[],"triangles":[]}
]}
```

Toegestane lagen: `PH_DESIGN`, `PH_FACADES`, `PH_TARGET`, `REFERENCE_CONTEXT`.
De huidige completed-run viewer is bewijs uit een afgeronde run, geen importpreview.
Camera-acties en laagzichtbaarheid mogen plaatsing/berekening nooit wijzigen.
`PDOK_AERIAL` is een afzonderlijk lokaal texturepakket, geen scenelaag of
Grasshopper-input. Captures moeten de contextmanifest- en afbeeldingshash binden.

### Desktopbeveiliging

- Alle desktoproutes en assets vereisen `X-ParkHaven-Session`.
- De token komt via stdin/WebView2-injectie, nooit in URL, projectbestand of JS.
- Houd assets same-origin en lokaal; geen CDN.
- Backendprocesstatus, HTTP-respons en runstatus zijn verschillende signalen.

### AI

- API-key is momenteel ephemeral en mag niet worden gelogd/opgeslagen.
- Deployment-specifieke AI-endpoints staan alleen in de genegeerde lokale
  trustconfiguratie of `PARKHAVEN_AI_ENDPOINT`, nooit in getrackte documentatie.
- Private TLS-trust is origin-bound en fingerprint-pinned. Schakel verificatie niet
  globaal uit en volg `docs/AI_TLS.md` bij certificaatrotatie.
- Huidige payload: ontwerpdoel, ongewijzigde metrics, begrensde geometrie/plaatsing
  en vier gelabelde dezelfde-run PNG's via OpenAI-compatible `image_url` content.
- `view-evidence.json`, alle onderliggende hashes en stabiele IDs worden vlak voor
  verzending opnieuw gevalideerd. Een tekst-only fallback is niet toegestaan.
- Claim geen live modelbegrip totdat Spark image-input en structured JSON met de
  gebruikerscredentials en het exacte model aantoonbaar heeft geaccepteerd.

## 7. Verificatie per wijziging

Begin met de kleinste relevante check; voer daarna regressies uit.

```powershell
# Python/API
.\.venv\Scripts\python.exe -m pytest -q

# Syntax
.\.venv\Scripts\python.exe -m compileall -q app tests scripts
node --check .\app\static\app.js
node --check .\app\static\viewer.js

# Web-UI / WebGL (Playwright staat in de analyser-venv)
& '..\ParkHaven_Analyzer_App_v0.2\.venv\Scripts\python.exe' .\tests\browser_workflow_smoke.py

# Builds via lokale SDK
& "$env:TEMP\opencode\dotnet-sdk\dotnet.exe" build .\desktop\ParkHaven.Desktop\ParkHaven.Desktop.csproj -c Release
& "$env:TEMP\opencode\dotnet-sdk\dotnet.exe" build .\rhino-plugin\ParkHaven.Rhino.csproj -c Release
```

Voer live Rhino-tests alleen uit wanneer de wijziging Rhino, geometrie, eenheden of
berekeningen raakt. Sluit eerst app-owned Rhino-sessies die de `.rhp` vergrendelen.
Stop uitsluitend processen die de test zelf startte.

Bekende niet-blokkerende waarschuwing: Starlette `TestClient`/httpx-deprecatie.
Noteer altijd exact welke checks wel en niet zijn uitgevoerd.

## 8. Token- en contextdiscipline

- Gebruik glob/grep vóór file reads; lees gerichte vensters rond treffers.
- Lees `progress.md` en `plan.md` niet telkens volledig opnieuw.
- Open geen `scene.json`, GHX of evidence-JSON volledig: deze bevatten zeer lange
  regels. Zoek keys of gebruik een klein regelvenster/script voor samenvattingen.
- Lees geen gegenereerde `bin/`, `obj/`, `.venv/`, caches of WebView2-profielen.
- Gebruik bestaande scripts/evidence in plaats van een live run te herhalen wanneer
  de taak geen nieuwe Rhino-eigenschap verandert.
- Herhaal geen onderzoek dat al met machineleesbaar bewijs in `docs/*.json` staat.
- Maak de kleinste correcte wijziging; voeg geen compatibility-laag toe zonder
  concrete bestaande data/consument.
- Bewaar geen geheimen in prompts, patches, logs, tests of documentatie.

## 9. Werk- en documentatieregels

- Onderzoek eerst, implementeer daarna end-to-end en verifieer.
- Gebruik `apply_patch` voor handmatige edits.
- Revert of wijzig geen onbekende/user changes. De analyser-worktree kan dirty zijn.
- Commit/push alleen op expliciet verzoek.
- Werk [`progress.md`](progress.md) bij:
  - bij de start van substantieel werk: scope en pending verificatie;
  - na een belangrijk checkpoint: feiten en tussentijdse teststatus;
  - aan het einde: resultaat, bewijs, beperkingen en exacte volgende stap.
- Werk `plan.md` alleen bij bij scope-, architectuur-, fase- of prioriteitswijziging.
- Claim niets als verified zonder uitgevoerde test of bestaand bewijs.

## 10. Compacte handoff-template

Gebruik bij onderbreking of contextlimiet:

```markdown
## Doel
<één zin>

## Gedaan
- <bestanden/gedrag>

## Bewijs
- `<commando>` → <resultaat>

## Openstaand/blokkade
- <concreet punt>

## Volgende actie
1. <exacte eerste stap>

## Relevante bestanden
- `<pad>`: <waarom>
```

Vermeld geen volledige logs of grote JSON-payloads; noteer paden en kernwaarden.
