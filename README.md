# 📦 Barcode → Bring! oder andere Einkaufsliste

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/Noack1978/Barcodescan-zu-Bring-.svg)](https://github.com/Noack1978/Barcodescan-zu-Bring-/releases)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io)

Barcode scannen mit **Binary Eye** → Home Assistant fügt das Produkt automatisch in deine **Bring!-Einkaufsliste** oder auch andere Einkaufsliste ein. **Keine manuelle YAML-Konfiguration nötig.**

> **v2.1.1** – Webhooks werden pro Benutzer eindeutig benannt

---

## ✅ Was automatisch eingerichtet wird

- Webhook-Empfänger mit **zufälliger, eindeutiger ID** (sicher, nicht erratbar)
- **Parallele** Abfrage von OpenFoodFacts, OpenBeautyFacts und OpenProductsFacts
- Eintrag in die gewählte Bring!-Liste
- Push-Benachrichtigung bei unbekanntem Produkt – an **alle** konfigurierten Geräte
- Serielle Verarbeitung mehrerer Scans über interne Queue – kein Scan geht verloren
- Doppelscan-Erkennung (gleicher Barcode zweimal schnell hintereinander)

---

## 🧰 Voraussetzungen

- Home Assistant 2024.1 oder neuer
- Android-App [Binary Eye](https://play.google.com/store/apps/details?id=de.markusfisch.android.binaryeye)
- Bring!-Integration installiert (liefert eine `todo.xxx`-Entity)
- es geht auch jede andere Einkaufsliste
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
3. **Schritt 1:** Benutzername eingeben, Bring!-Liste und Benachrichtigungsgeräte wählen
4. **Schritt 2:** Webhook-Aktivierungsanleitung lesen → **Fertig**
5. **Webhook aktivieren:** Einstellungen → Integrationen → Webhooks → Webhook `barcode_bring_xxxxxxxx` aktivieren → URL kopieren

Für **mehrere Benutzer** die Integration einfach erneut hinzufügen – jede Instanz erhält eine eigene Webhook-URL und eigene Benachrichtigungsgeräte.

---

## 👥 Mehrere Benutzer einrichten

Jeder Benutzer bekommt eine eigene Instanz der Integration mit eigenem Webhook,
eigener Bring!-Liste und eigenen Benachrichtigungsgeräten.

**Einrichtung für einen zweiten Benutzer (z. B. Sandra):**

1. **Einstellungen → Geräte & Dienste → + Integration hinzufügen**
2. Erneut „Barcode → Bring!" suchen und auswählen
3. **Schritt 1:** Anderen Benutzernamen eingeben (z. B. `Sandra`), Liste und Gerät wählen
4. **Schritt 2:** Webhook aktivieren – es wird ein **neuer** Webhook angelegt
5. Die neue Webhook-URL in **Sandras** Binary Eye eintragen

In Geräte & Dienste erscheinen dann zwei separate Einträge:
- `Barcode → Bring! (Mirko)` – mit Mirkos Webhook-URL und Handy
- `Barcode → Bring! (Sandra)` – mit Sandras Webhook-URL und Handy

Scannt Mirko einen Barcode, geht die Benachrichtigung nur an Mirkos Gerät –
und umgekehrt.

---

## 🔧 Konfiguration nachträglich ändern

Einstellungen → Geräte & Dienste → **Barcode → Bring! (Name)** → **Konfigurieren**

Dort können geändert werden:
- Benutzername
- Bring!-Liste
- Benachrichtigungsgeräte (hinzufügen oder entfernen)

Die Webhook-URL bleibt dabei unverändert – Binary Eye muss nicht neu eingerichtet werden.

---

## 📱 Binary Eye einrichten (einmalig manuell)

In Binary Eye unter **Einstellungen → Aktion bei Scan**:

| Einstellung  | Wert                                                        |
|--------------|-------------------------------------------------------------|
| Aktionstyp   | HTTP-POST                                                   |
| URL          | *(aus HA Webhooks kopieren – siehe Einrichtung Schritt 5)*  |
| Content-Type | `application/json`                                          |

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
→ Gefunden:       Eintrag in Bring!-Liste
→ Nicht gefunden: Push-Benachrichtigung an alle konfigurierten Geräte
```

---

## 💡 Hinweise

- Webhook-ID wird beim Setup zufällig generiert und bleibt dauerhaft erhalten
- Keine Helfer (`input_text`, `input_boolean`) oder REST-Sensoren nötig
- Kein YAML-Eintrag in `configuration.yaml` erforderlich
- Kompatibel mit jeder `todo`-Entity (nicht nur Bring!)
- Mehrere Benutzer möglich – je eine Integration pro Person

---

## 📋 Changelog

### v2.1.1
- Webhook-Name enthält jetzt den Benutzernamen (z. B. "Barcode Scan (Mirko)")

### v2.1.0
- Mehrere Benachrichtigungsgeräte gleichzeitig wählbar
- Konfiguration (Benutzername, Liste, Geräte) nachträglich änderbar ohne Neueinrichtung
- Webhook-URL bleibt bei Konfigurationsänderungen erhalten

### v2.0.0
Vollständige Neuentwicklung als native HA Custom Integration (HACS-kompatibel).
Kein YAML mehr nötig – alles läuft über den UI-Setup-Dialog.

### v1.x
YAML-basierte Lösung mit Automationen, Skripten und REST-Sensoren.

---

## 🧾 Lizenz

MIT License – freie Verwendung & Weitergabe

---

## 💬 Fragen?

[Issue auf GitHub öffnen](https://github.com/Noack1978/Barcodescan-zu-Bring-/issues)
