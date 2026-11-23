# BeatBee – Flask Web Workflow Specification

**Stand:** 23. November 2026  
**Status:** Geplante Web-Änderungen; noch nicht implementiert  
**Geltungsbereich:** Ausschließlich Flask-Web-App

## 1. Architektur und Zuständigkeiten

- Flask bleibt das Webframework. **Kein Streamlit**.
- Der bestehende Python Core sowie der Python-CLI-Workflow bleiben **unverändert**.
- Die Web-App darf vorhandene Python-Suchfunktionen wiederverwenden, besitzt jedoch ihren **eigenen interaktiven Workflow, Web-Status und JSON-Export**.
- Der Python Core bestimmt nicht die manuelle Ergebnisbestätigung der Web-App.
- Kein automatisches Publishing auf Discogs.

## 2. Initialer Ablauf

1. Benutzer lädt oder bearbeitet JSON mit `list_name` und geordneten `records`.
2. Benutzer startet die initiale Discogs-Suche über vorhandene Python-Funktionen.
3. Ein Eintrag ohne `type` wird mit dem Default `master` gesucht.
4. Der initiale Web-Ablauf verwendet den im jeweiligen Record angegebenen Suchtyp. Die bestehende Core-Unterstützung für Type-Arrays wird dadurch **nicht** verändert.
5. Die Web-App zeigt alle noch offenen Positionen gemeinsam im **nIO-Bereich**; alle erfolgreich aufgelösten Positionen stehen in der **iO-Tabelle**.
6. Original-JSON, ursprüngliche Positionsnummern und ursprüngliche Reihenfolge werden als unveränderliche Referenz bewahrt.

## 3. Web-Status: iO und nIO

- **iO (automatisch):** Durch die initiale Suche eindeutig aufgelöste Position.
- **nIO:** Noch nicht aufgelöste Position, unabhängig davon, ob der technische Core-Status `NOT_FOUND`, `MULTIPLE` oder `ERROR` lautet.
- **iO (manuell):** Der Benutzer hat ein konkretes Suchergebnis ausdrücklich bestätigt.
- Die technischen Core-Status dürfen zur Diagnose sichtbar bleiben, aber nIO wird **nicht mehr in getrennte Statusgruppen aufgeteilt**.
- Manuelles Web-iO bedeutet **nicht**, dass die Python-Core-Klassifikation nachträglich zu `OK` geändert wird.

## 4. Eine interaktive Fläche pro nIO-Position

Jede offene Position hat einen unabhängigen Bereich mit:

- ursprünglicher 1-basierter Positionsnummer und ursprünglichem Record;
- technischem Suchstatus/Fehlermeldung;
- bearbeitbaren unterstützten Suchparametern;
- Checkboxen für Ressourcentypen;
- eigenem Button **Erneut suchen**;
- Liste aller verfügbaren Treffer, ggf. mit Pagination;
- genau einer Radiobutton-Auswahl;
- Button **Auswahl bestätigen**.

Änderungen an Position A dürfen keine anderen Positionen oder deren Bestätigungen überschreiben.

## 5. Type-Checkboxen und Mehrfachsuche

Die nIO-Oberfläche bietet Checkboxen für:

- `master`
- `release`
- `artist`
- `label`

Mindestens ein Typ muss ausgewählt sein. Fehlt `type` im Original-Record, ist zunächst `master` aktiviert.

Bei **Erneut suchen** erzeugt die Web-App **eine separate Suchabfrage je ausgewähltem Typ** und verwendet die aktuell editierten Suchparameter. Alle Treffer sämtlicher ausgewählter Typen sollen erreichbar und auswählbar sein, **nicht nur die drei besten Master-Kandidaten**. Eine paginierte Darstellung ist zulässig, ein stilles Abschneiden der Treffermenge nicht.

Die Checkboxen dienen **nur der interaktiven Suche**. Sie bestimmen **nicht** das finale `type`-Feld beim Export.

Die Implementierung muss prüfen, ob die bestehenden Python-Schnittstellen vollständige Trefferlisten und Suchen für einzelne Positionen liefern. Fehlende Web-Anbindung darf ergänzt werden, ohne Python-Suchalgorithmen oder CLI-Verhalten zu ändern.

## 6. Ergebnisliste und Radiobutton-Bestätigung

Jeder Treffer zeigt, soweit vorhanden:

- tatsächlichen Ressourcentyp;
- Discogs-ID und Discogs-Link;
- Künstler bzw. Ressourcenbezeichnung;
- Titel;
- Jahr.

Der Benutzer kann **genau einen Treffer** je Position auswählen. Als finale Web-Ergebnisse werden `master`, `release`, `artist` und `label` gleichermaßen akzeptiert.

Erst der Klick auf **Auswahl bestätigen** bewirkt:

1. Speichern der zu diesem Zeitpunkt editierten Suchkriterien.
2. Speichern **genau des ausgewählten** Ressourcentyps, der Discogs-ID und der verfügbaren Treffer-Metadaten.
3. Änderung des Web-Status zu **iO – manuell bestätigt**.
4. Entfernen aus dem aktiven nIO-Bereich und Aufnahme in die iO-Tabelle.

Nicht ausgewählte Treffer oder weitere angekreuzte Types werden **nicht** exportiert. Eine neue Suche verwirft die bisher noch nicht bestätigte Radiobutton-Auswahl. Eine bereits bestätigte Auswahl bleibt gültig, bis der Benutzer dieselbe Position ausdrücklich neu bestätigt.

## 7. Gemeinsame iO-Tabelle

**Unterhalb** des nIO-Bereichs erscheint eine gemeinsame Liste aus automatisch eindeutigen und manuell bestätigten Ergebnissen.

Spalten:

| Spalte | Inhalt |
|---|---|
| Originalposition | 1-basierter Index in der hochgeladenen JSON-Datei |
| Artist / Name | Verfügbare Künstler- oder Ressourcenbezeichnung |
| Titel | Verfügbarer Titel |
| Jahr | Falls vorhanden |
| Type | Bestätigter Ressourcentyp |
| Discogs-ID | ID des Ergebnisses |
| Link | Passender Discogs-Link |
| Herkunft | Automatisch oder manuell bestätigt |

**Standard:** ursprüngliche JSON-Reihenfolge.

Interaktive Sortierung jeweils **aufsteigend oder absteigend** nach Originalposition, Artist/Name, Titel, Jahr, Type oder Discogs-ID. Bei gleichem Wert entscheidet die ursprüngliche Position stabil. **Eine Sortierung ändert ausschließlich die Anzeige, niemals die JSON-Exportreihenfolge.**

## 8. Eigenständiger Web-JSON-Export

Beim Export wird **eine neue JSON-Datei** erzeugt. Es gelten folgende Regeln:

- `list_name`, Anzahl der Records, Duplikate und **ursprüngliche Reihenfolge** bleiben erhalten.
- **Automatisch iO:** Ursprüngliche Suchparameter bleiben erhalten; automatisch gefundene Master-ID kann entsprechend dem bisherigen Web-Export übernommen werden.
- **Manuell bestätigtes nIO:** Der betreffende Record wird durch **die vom Benutzer bestätigten Suchparameter** ersetzt. `type` ist **ein einzelner String**, nämlich der Type des per Radiobutton gewählten Treffers. Die Auswahlreferenz enthält die tatsächliche Discogs-ID und ihren Ressourcentyp.
- **Noch offenes nIO:** Der Original-Record wird **unverändert** übernommen. Unbestätigte Entwürfe werden nicht exportiert.
- Der Export ist auch bei verbleibenden nIO-Positionen möglich; offene Positionen sind in der Weboberfläche klar erkennbar.
- Die Originaldatei wird nicht überschrieben.
- Die Web-Exportdatei ist ein **eigenständiges Web-Format**; sie muss nicht von der unveränderten Python-CLI als Eingabe akzeptiert werden.

**Vorgeschlagene Web-Auswahlreferenz:**

```json
{
  "artist": "Omega",
  "release_title": "10000 lépés",
  "type": "release",
  "selected_result": {
    "type": "release",
    "id": 67890,
    "url": "https://www.discogs.com/release/67890"
  }
}
```

`selected_result` ist **Web-Metadatum und kein Discogs-Suchparameter**. Die finale Implementierung muss eine konsistente Feldstruktur definieren und dokumentieren. Beim erneuten Laden eines Web-Exports dürfen Metadaten keinesfalls als Suchparameter an den unveränderten Python Core übergeben werden.

## 9. Session-State und Sicherheit

Pro Originalposition sind getrennt zu speichern: Original-Record, aktueller Bearbeitungsentwurf, aktivierte Type-Checkboxen, letzter Suchlauf, ausgewählter Kandidat und explizit bestätigter Web-Zustand.

- Keine gegenseitige Beeinflussung unterschiedlicher Positionen oder Browser-Sessions.
- Discogs-Token ausschließlich serverseitig; niemals in HTML, JavaScript, Antworten, Exporten oder Logs.
- Eingaben und Ausgabe-HTML sicher validieren bzw. escapen.
- API-Rate-Limits und kontrollierte Parallelität beachten.
- Keine automatische Veröffentlichung und keine Behauptung über erfolgte Discogs-Listenanlage.
- Ohne persistente Speicherung kann flüchtiger Session-Zustand verloren gehen; dies muss der UI klar sein.

## 10. Akzeptanzkriterien

1. Python Core und CLI bleiben unverändert; bestehende Tests bleiben grün.
2. Alle nIO-Positionen erscheinen in einem gemeinsamen Bereich.
3. Jede nIO-Position lässt sich unabhängig bearbeiten und einzeln suchen.
4. Mehrere Types können via Checkboxen gewählt werden; pro Type erfolgt eine eigene Suche.
5. Alle verfügbaren Treffer sind erreichbar, auch über Pagination.
6. Radiobutton und explizite Bestätigung übernehmen **genau ein** Master-, Release-, Artist- oder Label-Ergebnis.
7. Die bestätigte Position wird Web-iO, ohne den technischen Core-Status zu überschreiben.
8. Die gemeinsame iO-Tabelle erscheint darunter und lässt sich nach mehreren Kategorien auf- und absteigend sortieren.
9. Der Export behält die ursprüngliche JSON-Reihenfolge bei.
10. Nur ausdrücklich bestätigte Korrekturen ersetzen nIO-Records; der exportierte `type` ist der Type des **ausgewählten Treffers**, kein Checkbox-Array.
11. Offene nIO-Records bleiben originalgetreu erhalten.
12. Neue Web-Tests prüfen Suche, Mehrfachtypes, Radio-Auswahl, Statuswechsel, Sortierung, Export, Session-Isolation, Fehlerszenarien und Token-Schutz.

## 11. Implementierungsabgrenzung

Dies ist die **Soll-Spezifikation**, nicht der Nachweis einer bereits erfolgten Codeänderung. Vor der Implementierung sind insbesondere die tatsächlichen Schnittstellen für Einzelpositionssuche und vollständige Trefferlisten zu prüfen. Frühere Streamlit-Planungen sind für diesen Flask-Web-Workflow nicht maßgeblich. Die Dateien `SPEC.md` und der Python-CLI-Workflow werden nicht geändert.
