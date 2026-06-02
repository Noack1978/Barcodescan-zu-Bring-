"""Konstanten für Barcode → Bring! Integration."""

DOMAIN = "barcode_bring"

CONF_USER_NAME = "user_name"
CONF_BRING_LIST = "bring_list"
CONF_NOTIFY_SERVICES = "notify_services"  # Liste statt einzelner String
CONF_WEBHOOK_ID = "webhook_id"
CONF_CLOUDHOOK_URL = "cloudhook_url"

# API URLs
API_OPENFOOD = "https://world.openfoodfacts.org/api/v0/product/{}.json"
API_OPENBEAUTY = "https://world.openbeautyfacts.org/api/v0/product/{}.json"
API_OPENPRODUCTS = "https://world.openproductsfacts.org/api/v2/product/{}.json"

UNKNOWN_VALUES = {"Unbekannt", "Unknown", "unavailable", "unknown", ""}
