# BeatBee

BeatBee prüft eine geordnete Liste von Discogs-Suchanfragen und sucht zuerst
nach **Master-Releases**. Nur wenn die vollständige Master-Suche keine Treffer
liefert, wird zusätzlich eine Discogs-Release-Suche als Album-Fallback ausgeführt.
Die Release-Treffer sind diagnostische Links, keine Master-Treffer. Eine lokale
HTML-Zusammenfassung zeigt Ergebnisse, Probleme und anklickbare Discogs-Links.

BeatBee erstellt **keine Discogs-Liste automatisch**: Eine unterstützte
Schreibschnittstelle für User Lists ist derzeit nicht bestätigt. Bei vollständig
eindeutigen Ergebnissen kannst du eine Liste exportieren und sie auf Discogs
manuell anlegen.

## Voraussetzungen

- Python 3.11 oder neuer
- Internetverbindung und ein Discogs-Konto
- Ein persönlicher Discogs-Token für die API-Suche

Das Programm verwendet die Python-Standardbibliothek; für den Start über
`main.py` müssen keine zusätzlichen Pakete installiert werden.

## Discogs-Token erstellen

1. Melde dich auf [Discogs](https://www.discogs.com/) an.
2. Öffne die [Discogs-Entwicklereinstellungen](https://www.discogs.com/settings/developers).
3. Erstelle unter **Personal Access Token** bzw. **User Token** über
   **Generate token** einen persönlichen Token. Die Beschriftung kann sich ändern.
4. Kopiere den Token und behandle ihn wie ein Passwort.

Quelle: [Discogs API Authentication](https://www.discogs.com/developers/#page:authentication).

### Token in JSON eintragen

Erstelle oder bearbeite `discogsToken.json` im Projektordner:

```json
{
  "discogs_token": "HIER_DEINEN_TOKEN_EINTRAGEN"
}
```

Der Wert ist ein Platzhalter: Ersetze ihn durch deinen eigenen Token.
`discogsToken.json` ist in `.gitignore` eingetragen. Gib den Token nicht weiter
und lade die Datei nicht in Git oder öffentliche Logs hoch. Falls ein Token
versehentlich veröffentlicht wurde, widerrufe ihn bei Discogs und erstelle
einen neuen.

### Alternative: Umgebungsvariable

Für die aktuelle PowerShell-Sitzung:

```powershell
$env:DISCOGS_TOKEN = "HIER_DEINEN_TOKEN_EINTRAGEN"
```

`DISCOGS_TOKEN` hat Vorrang vor der Token-Datei. Vermeide es, echte Tokens in
Skripten oder gemeinsam genutzten Terminalprotokollen zu speichern.

## Eingabe: Suchliste

Lege im Projektordner eine UTF-8-Datei `discogsList.json` an oder bearbeite sie:

```json
{
  "list_name": "Meine Albumliste",
  "records": [
    {"artist": "Gábor Szabó", "release_title": "Dreams", "year": "1968"},
    {"artist": "Omega", "release_title": "10000 lépés", "year": "1969"}
  ]
}
```

| Angabe | Bedeutung |
| --- | --- |
| `list_name` | Nicht leerer Name der Liste; Unicode und Schreibweise bleiben erhalten. |
| `records` | Nicht leere, geordnete Liste von Suchobjekten. Jedes Objekt ist eine eigenständige Discogs-Suche. |
| `artist` | Suchbegriff für den Künstler. |
| `release_title` | Suchbegriff für den Album- bzw. Release-Titel. |
| `year` | Erscheinungsjahr als Zeichenkette oder ganze Zahl. |
| `q` | Allgemeiner Suchbegriff, alternativ oder zusätzlich zu anderen Suchfeldern. |

`artist`, `release_title`, `year` und `q` sind Beispiele, keine Pflichtfelder.
Weitere derzeit akzeptierte Suchparameter sind `title`, `genre`, `style`,
`country`, `format`, `label`, `catno`, `barcode`, `track`, `credit`, `anv`,
`submitter` und `contributor`. Die Werte müssen nicht leere Zeichenketten oder
ganze Zahlen sein. Ein Suchobjekt darf nicht leer sein.

BeatBee sucht zuerst mit `type=master`; `type: "master"` ist in der Eingabe
optional erlaubt, andere Typen werden abgelehnt. Für den Album-Fallback setzt
BeatBee selbst `type=release`, ohne die Eingabe zu verändern. `page` und
`per_page` verwaltet BeatBee selbst. Unbekannte Felder und ungültiges JSON
werden vor der ersten API-Anfrage abgewiesen. Reihenfolge und doppelte Einträge
bleiben erhalten.

## Start und Ablauf

Im Projektordner:

```powershell
python main.py
```

Alternativ mit einer vorhandenen virtuellen Umgebung:

```powershell
.venv\Scripts\python.exe main.py
```

Ohne Argumente verwendet das Programm `discogsList.json` und den Token aus
`DISCOGS_TOKEN` oder `discogsToken.json`. Eine andere Eingabedatei kannst du
ausdrücklich angeben:

```powershell
python main.py validate meine-liste.json
python main.py --help
```

Während der Suche zeigt das Terminal einen Fortschrittsbalken mit Prozentsatz und
Anzahl bearbeiteter Einträge. Auch fehlgeschlagene Suchen zählen als bearbeitet.
Anschließend wird der Pfad des HTML-Berichts ausgegeben. Für
`discogsList.json` heißt er `discogsList.summary.html` und liegt neben der
Eingabedatei. Öffne ihn lokal im Browser; ein Webserver ist nicht nötig. Ein
erneuter Lauf ersetzt den vorherigen Bericht.

BeatBee begrenzt Discogs-Anfragen auf mindestens 1,25 Sekunden Abstand und
berücksichtigt die Rate-Limit-Header. Bei HTTP `429` wartet es entsprechend
`Retry-After`, andernfalls 60 Sekunden, und versucht die Anfrage erneut.
Sehr lange serverseitige Wartezeiten über fünf Minuten werden als Fehler
ausgegeben; BeatBee sendet während der Sperrzeit keine weiteren Anfragen.
Die Begrenzung gilt pro Programmlauf; parallele Programme können sich
dennoch gegenseitig ins Rate-Limit bringen.

## HTML-Bericht verstehen

Der Bericht enthält die Listenbezeichnung, Gesamt- und Statuszahlen sowie alle
Einträge in diesen Gruppen:

- **OK:** Genau eine eindeutige Master-ID wurde gefunden.
- **NOT_FOUND:** Keine Master-ID wurde gefunden. BeatBee sucht dann zusätzlich
  nach Discogs-Releases und zeigt höchstens drei Links als Diagnose. Die Suche
  ist nicht auf das Discogs-Format „Album“ beschränkt. Release-Treffer zählen
  nicht als Master-Treffer und können nicht exportiert werden.
- **MULTIPLE:** Mehr als eine eindeutige Master-ID wurde gefunden. Bis zu drei
  deterministisch sortierte Kandidaten mit Links dienen nur als Hinweise;
  BeatBee wählt keinen davon aus.
- **ERROR:** Eine erforderliche Suche war technisch fehlerhaft oder
  unvollständig, etwa durch ein Netzwerkproblem oder ein erreichtes Suchlimit.

Am Ende stehen die `OK`-Master in ursprünglicher Reihenfolge mit Künstler,
Album, Master-ID und Discogs-Hyperlink. Künstler und Album sind entsprechend
gekennzeichnet, wenn sie aus dem Discogs-Suchtitel abgeleitet oder aus der
Suchanfrage übernommen wurden. Fehlende Angaben werden als nicht verfügbar
gezeigt. Suchergebnisse werden anhand der Anzahl eindeutiger Master-IDs
klassifiziert, nicht durch eine zusätzliche semantische Prüfung von Titel oder
Jahr.

Bei `NOT_FOUND` oder `MULTIPLE` bearbeitest du die Suchparameter selbst in
der JSON-Datei und startest die Prüfung erneut. Bei `ERROR` prüfe die Verbindung
oder den Token und versuche es erneut. Der Bericht enthält außerdem eine
maschinenlesbare JSON-Zusammenfassung; bei ausschließlich `OK`-Ergebnissen ist
darin auch das geordnete Manifest enthalten.

## Manuelle Discogs-Liste und Export

Erst wenn **alle** Einträge `OK` sind, kannst du eine geordnete Checkliste oder
ein JSON-Manifest exportieren:

```powershell
python main.py export discogsList.json --format markdown --output beatbee-list.md
python main.py export discogsList.json --format json --output beatbee-list.json
```

Die Markdown-Checkliste enthält Master-Links; das JSON enthält den Listennamen
und die Master-IDs in Eingabereihenfolge. Erstelle die Liste anschließend selbst
auf Discogs und übertrage die Einträge in dieser Reihenfolge. Der Export ist
**keine Veröffentlichung**.

`python main.py run discogsList.json` prüft ebenfalls die Liste und erreicht bei
vollständig eindeutigen Ergebnissen die Publishing-Grenze. Da kein verifizierter
Publisher verfügbar ist, meldet `run` derzeit „Publishing unavailable“ und
beendet sich mit Code `4`. Optional schreibt `--manifest DATEI.json` dann ein
Manifest. Kein nicht-`OK`-Ergebnis darf veröffentlicht werden.

## Exit-Codes

| Code | Bedeutung |
| --- | --- |
| `0` | Validierung oder manueller Export erfolgreich. |
| `1` | Mindestens ein Eintrag ist `NOT_FOUND` oder `MULTIPLE`. |
| `2` | Die Eingabe ist ungültig oder kann nicht gelesen werden. |
| `3` | Mindestens eine Suche ist `ERROR` oder der HTML-Bericht konnte nicht geschrieben werden. |
| `4` | Publishing ist fehlgeschlagen oder nicht verfügbar. |

## Projektdateien und Git

Ins Repository gehören `main.py`, `pyproject.toml`, `src/beatbee/`, `tests/`,
`README.md`, `SPEC.md`, `docs/`, `.gitignore` und die Projektanweisungen in
`.github/`. Für den Standardstart ohne Argumente wird außerdem
`discogsList.json` benötigt; alternativ legst du diese Datei nach dem Klonen
selbst an oder gibst eine andere Eingabedatei an. Die Datei ist nicht ignoriert:
Prüfe ihren Inhalt, bevor du sie committest und hochlädst.

Die Token-Datei `discogsToken.json`, `.venv/`, Python-Caches, Build-Dateien,
HTML-Berichte `*.summary.html` und die oben gezeigten Exportdateien bleiben
durch `.gitignore` lokal. Der Token muss nach einem frischen Klon selbst
eingerichtet werden. Andere frei gewählte Exportdateien sind nicht automatisch
ignoriert und sollten vor einem Commit geprüft werden.

## Tests

Die Tests verwenden simulierte Discogs-Antworten und benötigen keinen Token.
Im Projektordner unter PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -p "test_*.py"
```

## Weitere Dokumentation

- [Spezifikation](SPEC.md)
- [Suchstrategie](docs/SEARCH_STRATEGY.md)
- [Publishing und Machbarkeitsprüfung](docs/PUBLISHING.md)
- [Architektur](docs/ARCHITECTURE.md)
- [Entscheidungen](docs/DECISIONS.md)
- [Offene Fragen](docs/OPEN_QUESTIONS.md)
- [Roadmap](docs/ROADMAP.md)
