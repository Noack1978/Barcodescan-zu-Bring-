# 📦 Barcode → Bring! Einkaufsliste

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/Noack1978/Barcodescan-zu-Bring-.svg)](https://github.com/Noack1978/Barcodescan-zu-Bring-/releases)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io)

Barcode scannen mit **Binary Eye** → Home Assistant fügt das Produkt automatisch in deine **Bring!-Einkaufsliste** ein. **Keine manuelle YAML-Konfiguration nötig.**

> **v2.0.0** – Vollständige Neuentwicklung als native HA Custom Integration

---

## ✅ Was automatisch eingerichtet wird

- Webhook-Empfänger mit **zufälliger, eindeutiger ID** (sicher, nicht erratbar)
- **Parallele** Abfrage von OpenFoodFacts, OpenBeautyFacts und OpenProductsFacts
- Eintrag in deine gewählte `todo`-Liste
- Push-Benachrichtigung bei unbekanntem Produkt
- Serielle Verarbeitung mehrerer Scans über eine interne Queue – kein Datenverlust

---

## 🧰 Voraussetzungen

- Home Assistant 2024.1 oder neuer
- Android-App [Binary Eye](https://play.google.com/store/apps/details?id=de.markusfisch.android.binaryeye)
- Bring!-Integration installiert (liefert eine `todo.xxx`-Entity)
- Home Assistant Companion App (für Push-Benachrichtigungen)

---

## 📥 Installation über HACS

1. HACS öffnen → **Integrationen** → ⋮ → **Benutzerdefinierte Repositories**
2. URL eingeben: `https://github.com/Noack1978/Barcodescan-zu-Bring-`
3. Kategorie: **Integration**
4. **Hinzufügen** → Integration suchen und installieren
5. Home Assistant **neu starten**

---

## ⚙️ Einrichtung

1. **Einstellungen → Geräte & Dienste → + Integration hinzufügen**
2. Nach „Barcode → Bring!" suchen
3. **Schritt 1:** Bring!-Liste und Benachrichtigungsdienst aus den Dropdowns wählen
4. **Schritt 2:** Die angezeigte Webhook-URL in Binary Eye eintragen
5. Fertig – kein Neustart erforderlich

---

## 📱 Binary Eye einrichten (einmalig manuell)

In Binary Eye unter **Einstellungen → Aktion bei Scan**:

| Einstellung  | Wert                                          |
|--------------|-----------------------------------------------|
| Aktionstyp   | HTTP-POST                                     |
| URL          | *(wird im Setup-Dialog angezeigt)*            |
| Content-Type | `application/json`                            |
| Body         | `{"content": "$barcode$"}`                    |

Die vollständige Webhook-URL (lokal und ggf. Nabu Casa) wird direkt im zweiten Schritt des Setup-Dialogs angezeigt.

---

## 🔄 Ablauf

```
Barcode scannen (Binary Eye)
        ↓
Webhook empfangen → sofort in Queue eingereiht
        ↓
OpenFoodFacts + OpenBeautyFacts + OpenProductsFacts parallel abfragen
        ↓
Ersten gefundenen Produktnamen verwenden
        ↓
→ Gefunden:      Eintrag in Bring!-Liste
→ Nicht gefunden: Push-Benachrichtigung
```

Mehrere Scans hintereinander werden seriell aus der Queue verarbeitet – kein Scan geht verloren. Identische Barcodes in schneller Folge (Doppelscan) werden automatisch erkannt und nur einmal verarbeitet.

---

## 💡 Hinweise

- Webhook-ID wird beim Setup zufällig generiert und bleibt dauerhaft erhalten
- Keine Helfer (`input_text`, `input_boolean`) oder REST-Sensoren nötig
- Kein YAML-Eintrag in `configuration.yaml` erforderlich
- Kompatibel mit jeder `todo`-Entity (nicht nur Bring!)

---

## 📋 Changelog

### v2.0.0
Vollständige Neuentwicklung als native HA Custom Integration (HACS-kompatibel).
Siehe [Release Notes](https://github.com/Noack1978/Barcodescan-zu-Bring-/releases/tag/v2.0.0) für Details.

### v1.x
YAML-basierte Lösung mit Automationen, Skripten und REST-Sensoren.

---

## 🧾 Lizenz

MIT License – freie Verwendung & Weitergabe

---

## 💬 Fragen?

[Issue auf GitHub öffnen](https://github.com/Noack1978/Barcodescan-zu-Bring-/issues)
