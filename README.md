# Barcode-Scan zu Bring! / Home Assistant Integration

Mit dieser Integration kannst du mithilfe der App *Binary Eye* Barcodes scannen und Ã¼ber einen Webhook an Home Assistant senden. Das Produkt wird automatisch identifiziert und zur Einkaufsliste (z.â€¯B. Bring! oder Home Assistant Todo) hinzugefÃ¼gt.

## Voraussetzungen

- Home Assistant
- REST-API Zugriff erlaubt
- App: [Binary Eye](https://play.google.com/store/apps/details?id=de.markusfisch.android.binaryeye)
- Integration einer Einkaufsliste (`todo`, z.â€¯B. Bring! oder HA Todo)
- Zwei REST-Sensoren:
  - `sensor.openfoodfacts_product_name`
  - `sensor.openbeautyfacts_product_name`

## Notwendige Helfer

- `input_text.last_barcode`  
- `input_boolean.barcode_processing`

## Sensoren (in `sensor.yaml` oder UI)

```yaml
- platform: rest
  name: openfoodfacts_product_name
  resource_template: "https://world.openfoodfacts.org/api/v0/product/{{ states('input_text.last_barcode') }}.json"
  value_template: >
    {% if value_json.status == 1 %}
      {{ value_json.product.product_name | default('Unbekannt') }}
    {% else %}
      Unbekannt
    {% endif %}
  scan_interval: 10

- platform: rest
  name: openbeautyfacts_product_name
  resource_template: "https://world.openbeautyfacts.org/api/v0/product/{{ states('input_text.last_barcode') }}.json"
  value_template: >
    {% if value_json.status == 1 %}
      {{ value_json.product.product_name | default('Unbekannt') }}
    {% else %}
      Unbekannt
    {% endif %}
  scan_interval: 10
```

## HTTP-Request in Binary Eye

POST an URL (ersetzt `<TOKEN>` durch deinen Webhook):

```
http://<HA_IP>:8123/api/webhook/barcode_scan?content={CODE}
```

Header:
```
Content-Type: application/json
```

## Beispiel Automatisierungsskript

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
        {% set name1 = states('sensor.openfoodfacts_product_name') %}
        {% set name2 = states('sensor.openbeautyfacts_product_name') %}
        {% if name1 not in ['Unbekannt', 'Unknown', ''] %}
          {{ name1 }}
        {% elif name2 not in ['Unbekannt', 'Unknown', ''] %}
          {{ name2 }}
        {% else %}
          Unbekannt
        {% endif %}

  - choose:
      - conditions:
          - condition: template
            value_template: >-
              {% set name1 = states('sensor.openfoodfacts_product_name') %}
              {% set name2 = states('sensor.openbeautyfacts_product_name') %}
              {% set produktname = (name1 if name1 not in ['Unbekannt', 'Unknown', ''] else (name2 if name2 not in ['Unbekannt', 'Unknown', ''] else 'Unbekannt')) %}
              {{ produktname in ['Unbekannt', 'Unknown', ''] }}
        sequence:
          - data:
              title: Produkt nicht gefunden
              message: |
                Barcode {{ barcode }} konnte keinem Produkt zugeordnet werden.
            action: notify.mobile_app_<dein_gerÃ¤t>
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
                  entity_id: todo.einkaufsliste
                  item: "{{ produktname | trim }}"
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
