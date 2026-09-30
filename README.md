# Westnetz MeDaCo für Home Assistant

Custom Integration, die die Smart-Meter-Daten (intelligentes Messsystem) aus dem
MeDaCo-Portal von Westnetz bzw. Westenergie Metering abholt und als
Langzeitstatistik in Home Assistant schreibt. Die Werte lassen sich direkt im
Energie-Dashboard als Netzbezug und Netzeinspeisung auswählen.

> **Status:** Grundgerüst. Login und Datenabruf (`api.py`) sind noch
> Platzhalter, bis die echten Portal-Endpunkte aus einem Browser-Mitschnitt
> übernommen sind.

## Wie es funktioniert

- Alle 4 Stunden meldet sich die Integration am Portal an und holt die
  15-Minuten-Werte seit dem letzten Import (beim ersten Start 90 Tage).
- Die Werte werden zu Stundenwerten zusammengefasst und als externe Statistik
  `medaco:<zählpunkt>_1_8_0` (Bezug) bzw. `..._2_8_0` (Einspeisung) importiert.
  Stunden werden erst übernommen, wenn alle vier Viertelstunden vorliegen.
- Weil das Portal die Daten verzögert liefert (meist am Folgetag), erscheinen
  sie im Energie-Dashboard rückwirkend zur richtigen Uhrzeit.
- Pro Zählpunkt gibt es zwei Diagnose-Sensoren: importierter Zählerstand und
  Datenstand (letzte vollständige Stunde).

## Installation (HACS)

1. HACS → Integrationen → Menü → Benutzerdefinierte Repositories →
   `https://github.com/DGne-Nurag/medaco2ha`, Kategorie „Integration“.
2. „Westnetz MeDaCo“ installieren und Home Assistant neu starten.
3. Einstellungen → Geräte & Dienste → Integration hinzufügen → „Westnetz MeDaCo“,
   Portal wählen und mit den MeDaCo-Zugangsdaten anmelden.
4. Energie-Dashboard → Netzverbrauch hinzufügen → Statistik „… Bezug“ wählen.

## Entwicklung

```bash
pip install pytest aiohttp
pytest -q
```
