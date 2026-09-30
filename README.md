# Westnetz MeDaCo für Home Assistant

Custom Integration, die die Smart-Meter-Daten (intelligentes Messsystem) aus dem
MeDaCo-Portal von Westnetz bzw. Westenergie Metering abholt und als
Langzeitstatistik in Home Assistant schreibt. Die Werte lassen sich direkt im
Energie-Dashboard als Netzbezug und Netzeinspeisung auswählen.

> **Status:** Erste Version. Login und Datenabruf sind aus einer echten
> Portal-Sitzung nachgebaut, aber noch nicht gegen das Live-Portal aus Home
> Assistant heraus getestet.

## Wie es funktioniert

- Die Integration meldet sich wie der Browser am Portal an (Formular-Login)
  und liest die Zählpunkte und ihre Messreihen aus.
- Alle 15 Minuten holt sie die Viertelstundenwerte der Register 1.29.0 (Bezug)
  und 2.29.0 (Einspeisung) seit dem letzten Import, beim ersten Start die
  letzten 365 Tage.
- Die Werte werden zu Stundenwerten zusammengefasst und als externe Statistik
  `medaco:<zählpunkt>_1_1_1_29_0` (Bezug) bzw. `..._2_29_0` (Einspeisung)
  importiert. Eine Stunde wird erst übernommen, wenn alle vier Viertelstunden
  vorliegen. Kommen Werte verspätet, werden sie rückwirkend zur richtigen
  Uhrzeit eingetragen.
- Ersatzwerte (Status „E“) übernimmt die Integration wie normale Werte. Wenn
  der Netzbetreiber sie später korrigiert, wird das nicht nachgezogen.
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
pip install pytest-homeassistant-custom-component
pytest -q
```

Die Tests prüfen das Auslesen der Portal-Antworten und starten die
Integration in einem Test-Home-Assistant gegen ein simuliertes Portal.
