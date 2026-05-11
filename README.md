# 📦 Barcode-Scan → Bring!-Einkaufsliste (Home Assistant + Binary Eye)

Mit dieser Integration kannst du mithilfe der Android-App **Binary Eye** einen Barcode scannen, und Home Assistant fügt das erkannte Produkt automatisch deiner **Bring!-Einkaufsliste** hinzu.

---

## 🧰 Voraussetzungen

* Home Assistant (lokal erreichbar)
* Android-App [Binary Eye](https://play.google.com/store/apps/details?id=de.markusfisch.android.binaryeye)
* REST-API Zugriff auf OpenFoodFacts, OpenBeautyFacts und OpenProductFacts
* Bring!-Integration (`todo.kaufland` oder andere Liste)

---

## 🛠️ Benötigte Helfer (Helpers)

Diese Helfer müssen in `input_text.yaml` und `input_boolean.yaml` (oder per UI) angelegt werden:

**`input_boolean.yaml`**
```yaml
barcode_processing:
  name: Barcode wird verarbeitet
  initial: false
```

**`input_text.yaml`**
```yaml
last_barcode:
  name: Letzter gescannter Barcode
  max: 20
```

---

## 🌐 REST-Sensoren für Produkterkennung (`sensors.yaml`)

> ⚠️ `scan_interval: 86400` bedeutet, die Sensoren pollen **nicht** automatisch.  
> Der Update wird ausschließlich per `homeassistant.update_entity` in der Automation ausgelöst – genau dann, wenn ein Barcode gescannt wurde.

```yaml
- platform: rest
  name: openfoodfacts_product_name
  resource_template: "https://world.openfoodfacts.org/api/v0/product/{{ states('input_text.last_barcode') }}.json"
  value_template: >
    {% if value_json is defined and value_json.status is defined and value_json.status == 1 %}
      {% set name = value_json.product.product_name | default('') %}
      {% set brand = value_json.product.brands | default('') %}
      {% set qty = value_json.product.quantity | default('') %}
      {% set result = [name, brand, qty] | select('ne', '') | list | join(' – ') %}
      {{ result if result else 'Unbekannt' }}
    {% else %}
      Unbekannt
    {% endif %}
  scan_interval: 86400

- platform: rest
  name: openbeautyfacts_product_name
  resource_template: "https://world.openbeautyfacts.org/api/v0/product/{{ states('input_text.last_barcode') }}.json"
  value_template: >
    {% if value_json is defined and value_json.status is defined and value_json.status == 1 %}
      {% set name = value_json.product.product_name | default('') %}
      {% set brand = value_json.product.brands | default('') %}
      {% set qty = value_json.product.quantity | default('') %}
      {% set result = [name, brand, qty] | select('ne', '') | list | join(' – ') %}
      {{ result if result else 'Unbekannt' }}
    {% else %}
      Unbekannt
    {% endif %}
  scan_interval: 86400

- platform: rest
  name: openproductsfacts_product_name
  resource_template: "https://world.openproductsfacts.org/api/v2/product/{{ states('input_text.last_barcode') }}.json"
  value_template: >
    {% if value_json is defined and value_json.status is defined and value_json.status == 1 %}
      {% set name = value_json.product.product_name | default('') %}
      {% set brand = value_json.product.brands | default('') %}
      {% set qty = value_json.product.quantity | default('') %}
      {% set result = [name, brand, qty] | select('ne', '') | list | join(' – ') %}
      {{ result if result else 'Unbekannt' }}
    {% else %}
      Unbekannt
    {% endif %}
  scan_interval: 86400
```

---

## 🤖 Automation: Barcode → Sensoren aktualisieren → Skript starten (`automations.yaml`)

```yaml
alias: Barcode → bring barcode speichern

triggers:
  - webhook_id: barcode_scan
    allowed_methods:
      - POST
    local_only: false
    trigger: webhook

actions:

  # Maximal 1 Minute warten bis Verarbeitung frei ist
  - wait_template: >
      {{ is_state('input_boolean.barcode_processing', 'off') }}
    timeout: "00:01:00"
    continue_on_timeout: true

  # Falls Verarbeitung weiterhin blockiert ist
  - if:
      - condition: state
        entity_id: input_boolean.barcode_processing
        state: "on"
    then:

      # Push-Nachricht mit Aktionen
      - action: notify.mobile_app_mirko_s_handy
        data:
          title: Barcode Verarbeitung blockiert
          message: >
            Die Barcode-Verarbeitung läuft seit über 1 Minute.
          data:
            actions:
              - action: BARCODE_ABORT
                title: Abbrechen

              - action: BARCODE_UNLOCK
                title: Verarbeitung freigeben

      # Auf Antwort warten
      - wait_for_trigger:

          - trigger: event
            event_type: mobile_app_notification_action
            event_data:
              action: BARCODE_ABORT

          - trigger: event
            event_type: mobile_app_notification_action
            event_data:
              action: BARCODE_UNLOCK

      # Verarbeitung freigeben
      - if:
          - condition: template
            value_template: >
              {{ wait.trigger.event.data.action == 'BARCODE_UNLOCK' }}
        then:
          - action: input_boolean.turn_off
            target:
              entity_id: input_boolean.barcode_processing

      # Automation abbrechen
      - if:
          - condition: template
            value_template: >
              {{ wait.trigger.event.data.action == 'BARCODE_ABORT' }}
        then:
          - stop: Benutzer hat die Verarbeitung abgebrochen

  # Barcode speichern
  - action: input_text.set_value
    target:
      entity_id: input_text.last_barcode
    data:
      value: "{{ trigger.json.content }}"

  # Produktsensoren aktualisieren
  - action: homeassistant.update_entity
    target:
      entity_id:
        - sensor.openfoodfacts_product_name
        - sensor.openbeautyfacts_product_name
        - sensor.openproductsfacts_product_name

  - delay: "00:00:05"

  # Weiterverarbeitung starten
  - action: script.bring_barcode_verarbeiten

mode: queued
max: 10
```

---

## 📜 Skript: bring\_barcode\_verarbeiten (`scripts.yaml`)

```yaml
alias: bring_barcode_verarbeiten
mode: queued
sequence:
  - action: input_boolean.turn_on
    target:
      entity_id: input_boolean.barcode_processing

  - variables:
      barcode: "{{ states('input_text.last_barcode') }}"
      produktname: >-
        {% set name1 = states('sensor.openfoodfacts_product_name') %}
        {% set name2 = states('sensor.openbeautyfacts_product_name') %}
        {% set name3 = states('sensor.openproductsfacts_product_name') %}
        {% if name1 not in ['Unbekannt', 'Unknown', ''] %}
          {{ name1 }}
        {% elif name2 not in ['Unbekannt', 'Unknown', ''] %}
          {{ name2 }}
        {% elif name3 not in ['Unbekannt', 'Unknown', ''] %}
          {{ name3 }}
        {% else %}
          Unbekannt
        {% endif %}

  - choose:
      - conditions:
          - condition: template
            value_template: "{{ produktname in ['Unbekannt', 'Unknown', ''] }}"
        sequence:
          - action: notify.mobile_app_mirko_s_handy
            data:
              title: Produkt nicht gefunden
              message: "Barcode {{ barcode }} konnte keinem Produkt zugeordnet werden."
          - action: input_text.set_value
            target:
              entity_id: input_text.last_barcode
            data:
              value: ""
          - action: input_boolean.turn_off
            target:
              entity_id: input_boolean.barcode_processing
    default:
      - action: todo.add_item
        data:
          entity_id: todo.kaufland
          item: "{{ produktname | regex_replace('[–—]', '-') }}"

      - action: input_text.set_value
        target:
          entity_id: input_text.last_barcode
        data:
          value: ""

      - action: input_boolean.turn_off
        target:
          entity_id: input_boolean.barcode_processing
```

---

## 📱 Binary Eye – Einrichtung

> Lade die App hier herunter:  
> 👉 [Binary Eye – Google Play](https://play.google.com/store/apps/details?id=de.markusfisch.android.binaryeye)

### 🔗 Webhook-URL:

```
http://<HOME_ASSISTANT_IP>:8123/api/webhook/barcode_scan?content=
```

> Ersetze `<HOME_ASSISTANT_IP>` durch die IP deines Home Assistant-Systems (z. B. `192.168.170.17`)  
> oder lass Nabu Casa einen Webhook-Link generieren (Companion-App → Cloud → Webhook), dann funktioniert es auch unterwegs.

### ⚙️ Einstellungen in Binary Eye:

* **Aktionstyp:** HTTP-POST
* **Methode:** `POST`
* **Content-Type:** `application/json`

---

## 🔄 Ablauf

```
Barcode scannen (Binary Eye)
        ↓
Webhook empfangen
        ↓
input_text.last_barcode = "4xxxxxxxxx"
        ↓
update_entity → alle 3 APIs werden JETZT abgefragt
        ↓
5s warten (API-Antwortzeit)
        ↓
Skript liest sensor.xxx → Produkt → Bring!
        ↓
input_text.last_barcode = "" (bereinigt)
```

---

## 💡 Hinweise & Tipps

* Die Sensoren pollen **nicht** automatisch – Updates erfolgen nur bei Barcode-Scan
* Der `barcode_processing`-Helfer verhindert gleichzeitige Verarbeitung bei mehreren Scans
* Du kannst das Skript erweitern, z. B. um:
  + Alexa-Sprachausgabe
  + Dashboard-Anzeige des letzten Scans
  + Unterscheidung verschiedener Produktkategorien

---

## 🧾 Lizenz

MIT License – freie Verwendung & Weitergabe

---

## 💬 Fragen?

Einfach ein Issue auf GitHub eröffnen oder über die Home Assistant Community Kontakt aufnehmen.
