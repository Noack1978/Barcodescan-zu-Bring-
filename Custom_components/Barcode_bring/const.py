"""Konstanten für Barcode → Bring! Integration."""

DOMAIN = "barcode_bring"

CONF_BRING_LIST = "bring_list"
CONF_NOTIFY_SERVICE = "notify_service"
CONF_WEBHOOK_ID = "webhook_id"

# API URLs
API_OPENFOOD = "https://world.openfoodfacts.org/api/v0/product/{}.json"
API_OPENBEAUTY = "https://world.openbeautyfacts.org/api/v0/product/{}.json"
API_OPENPRODUCTS = "https://world.openproductsfacts.org/api/v2/product/{}.json"

UNKNOWN_VALUES = {"Unbekannt", "Unknown", "unavailable", "unknown", ""}
