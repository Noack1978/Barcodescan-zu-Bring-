# 📦 Barcode-Scan → Bring!-Einkaufsliste (Home Assistant + Binary Eye)

Mit dieser Integration kannst du mithilfe der Android-App **Binary Eye** einen Barcode scannen, und Home Assistant fügt das erkannte Produkt automatisch deiner **Bring!-Einkaufsliste** hinzu.

---

## 🧰 Voraussetzungen

- Home Assistant (lokal erreichbar)
- Android-App [Binary Eye](https://play.google.com/store/apps/details?id=de.markusfisch.android.binaryeye)
- REST-API Zugriff auf OpenFoodFacts, OpenBeautyFacts und OpenProductFacts
- Bring!-Integration (`todo.kaufland` oder andere Liste)

---

## 🛠️ Benötigte Helfer (Helpers)

Diese zwei Helfer müssen in deiner `configuration.yaml`, `helpers.yaml` oder per UI angelegt werden:

```yaml
input_boolean:
  barcode_processing:
    name: Barcode wird verarbeitet
    initial: false

input_text:
  last_barcode:
    name: Letzter gescannter Barcode
    max: 20
```

---

## 🌐 REST-Sensoren für Produkterkennung

Füge diese Sensoren zu deiner `sensor.yaml` oder direkt in der Konfiguration hinzu:

```yaml
- platform: rest
  name: openfoodfacts_product_name
  resource_template: "https://world.openfoodfacts.org/api/v0/product/{{ states('input_text.last_barcode') }}.json"
  value_template: >
    {% if value_json.status == 1 %}
      {% set name = value_json.product.product_name | default('') %}
      {% set brand = value_json.product.brands | default('') %}
      {% set qty = value_json.product.quantity | default('') %}
      {% set result = [name, brand, qty] | select('string') | reject('equalto', '') | list | join(' – ') %}
      {{ result if result else 'Unbekannt' }}
    {% else %}
      Unbekannt
    {% endif %}
  scan_interval: 10

- platform: rest
  name: openbeautyfacts_product_name
  resource_template: "https://world.openbeautyfacts.org/api/v0/product/{{ states('input_text.last_barcode') }}.json"
  value_template: >
    {% if value_json.status == 1 %}
      {% set name = value_json.product.product_name | default('') %}
      {% set brand = value_json.product.brands | default('') %}
      {% set qty = value_json.product.quantity | default('') %}
      {% set result = [name, brand, qty] | select('string') | reject('equalto', '') | list | join(' – ') %}
      {{ result if result else 'Unbekannt' }}
    {% else %}
      Unbekannt
    {% endif %}
  scan_interval: 10
- platform: rest
  name: openproductsfacts_product_name
  resource_template: "https://world.openproductsfacts.org/api/v2/product/{{ states('input_text.last_barcode') }}.json"
  value_template: >
    {% if value_json.status == 1 %}
      {% set name = value_json.product.product_name | default('') %}
      {% set brand = value_json.product.brands | default('') %}
      {% set qty = value_json.product.quantity | default('') %}
      {% set result = [name, brand, qty] | select('string') | reject('equalto', '') | list | join(' – ') %}
      {{ result if result else 'Unbekannt' }}
    {% else %}
      Unbekannt
    {% endif %}
  scan_interval: 10
```

---

## 🤖 Automation: Barcode → Skript starten

```yaml
alias: Barcode → bring.barcode speichern
trigger:
  - platform: webhook
    webhook_id: barcode_scan
    allowed_methods:
      - POST
    local_only: false
condition:
  - condition: state
    entity_id: input_boolean.barcode_processing
    state: "off"
action:
  - service: input_boolean.turn_on
    target:
      entity_id: input_boolean.barcode_processing
  - service: input_text.set_value
    data:
      entity_id: input_text.last_barcode
      value: "{{ trigger.json.content }}"
  - delay: "00:00:10"
  - service: script.bring_barcode_verarbeiten
```

---

## 📜 Skript: bring_barcode_verarbeiten

```yaml
alias: bring_barcode_verarbeiten
mode: single
sequence:
  - target:
      entity_id: input_boolean.barcode_processing
    action: input_boolean.turn_on
    data: {}
  - variables:
      barcode: "{{ states('input_text.last_barcode') }}"
      produktname: >-
        {% set name1 = states('sensor.openfoodfacts_product_name') %}  {% set
        name2 = states('sensor.openbeautyfacts_product_name') %}  {% set name3 =
        states('sensor.openproductsfacts_product_name') %}  {% if name1 not in
        ['Unbekannt', 'Unknown', ''] %}
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
            value_template: >-
              {% set name1 = states('sensor.openfoodfacts_product_name') %} {%
              set name2 = states('sensor.openbeautyfacts_product_name') %} {%
              set name3 = states('sensor.openproductsfacts_product_name') %} {%
              set produktname = (name1 if name1 not in ['Unbekannt',
              'Unknown','']  else (name2 if name2 not in ['Unbekannt',
              'Unknown', '']  else (name3 if name3 not in ['Unbekannt',
              'Unknown', '']  else 'Unbekannt'))) %} {{ produktname in
              ['Unbekannt', 'Unknown', ''] }}
        sequence:
          - data:
              title: Produkt nicht gefunden
              message: |
                Barcode {{ barcode }} konnte keinem Produkt zugeordnet werden.
            action: notify.mobile_app_mirko_s_handy
          - delay: "00:00:01"
          - data:
              entity_id: input_text.last_barcode
              value: Unbekannt
            action: input_text.set_value
          - data:
              entity_id: input_boolean.barcode_processing
            action: input_boolean.turn_off
    default:
      - data:
          title: Barcode verarbeitet
          message: |
            Barcode: {{ barcode }}
            Produkt: {{ produktname }}
        action: persistent_notification.create
      - choose:
          - conditions:
              - condition: template
                value_template: "{{ produktname not in ['Unbekannt', 'Unknown', ''] }}"
            sequence:
              - data:
                  entity_id: todo.kaufland
                  item: "{{ produktname | regex_replace('[–—]', '-') }}"
                action: todo.add_item
      - delay: "00:00:01"
      - data:
          entity_id: input_text.last_barcode
          value: Unbekannt
        action: input_text.set_value
      - data:
          entity_id: input_boolean.barcode_processing
        action: input_boolean.turn_off
```

---

## 📱 Binary Eye – Einrichtung

> Lade die App hier herunter:  
> 👉 [Binary Eye – Google Play](https://play.google.com/store/apps/details?id=de.markusfisch.android.binaryeye)

### 🔗 Webhook-URL:

```
http://<HOME_ASSISTANT_IP>:8123/api/webhook/barcode_scan?content=
```

> Ersetze `<HOME_ASSISTANT_IP>` durch die IP deines Home Assistant-Systems (z. B. `192.168.170.17`)
> oder lass Nabu casa einen webhook link generieren (companion-App->cloud->webhook), dann funktioniert es auch unterwegs. 

### ⚙️ Einstellungen in Binary Eye:

- **Aktionstyp:** HTTP-POST  
- **Methode:** `POST`  
- **Content-Type:** `application/json`

---

## 💡 Hinweise & Tipps

- Du kannst das Skript erweitern, z. B. um:
  - Alexa-Sprachausgabe
  - Dashboard-Anzeige des letzten Scans
  - Unterscheidung verschiedener Produktkategorien
- Die Produktnamen werden nicht gespeichert, sondern direkt verarbeitet
- Der `barcode_processing`-Helfer verhindert gleichzeitige Verarbeitung bei mehreren Scans

---

## 🧾 Lizenz

MIT License – freie Verwendung & Weitergabe

---

## 💬 Fragen?

Einfach ein Issue auf GitHub eröffnen oder über die Home Assistant Community Kontakt aufnehmen.
