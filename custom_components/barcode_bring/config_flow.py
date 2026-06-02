"""Config Flow und Options Flow für Barcode → Bring! Integration."""
from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import cloud
from homeassistant.components.cloud import CloudNotAvailable, async_active_subscription
from homeassistant.components.webhook import async_generate_url
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_BRING_LIST,
    CONF_CLOUDHOOK_URL,
    CONF_NOTIFY_SERVICES,
    CONF_USER_NAME,
    CONF_WEBHOOK_ID,
    DOMAIN,
)

# ──────────────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ──────────────────────────────────────────────────────────────────────────────

def _get_todo_entities(hass: HomeAssistant) -> list[str]:
    """Alle vorhandenen todo-Entities ermitteln."""
    return sorted(
        state.entity_id
        for state in hass.states.async_all()
        if state.entity_id.startswith("todo.")
    )

def _get_notify_services(hass: HomeAssistant) -> list[str]:
    """Alle vorhandenen notify-Dienste ermitteln."""
    return sorted(
        f"notify.{name}"
        for name in (hass.services.async_services().get("notify") or {})
        if name not in ("send_message", "notify", "persistent_notification")
    )

def _build_schema(
    todo_entities: list[str],
    notify_services: list[str],
    current_user_name: str = "",
    current_bring_list: str = "",
    current_notify_services: list[str] | None = None,
) -> vol.Schema:
    """Schema mit HA-Selektoren bauen."""
    if current_notify_services is None:
        current_notify_services = []

    if todo_entities:
        bring_selector = SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=e, label=e) for e in todo_entities],
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
        bring_default = current_bring_list or todo_entities[0]
    else:
        bring_selector = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
        bring_default = current_bring_list or "todo.einkaufsliste"

    if notify_services:
        notify_selector = SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=s, label=s) for s in notify_services],
                multiple=True,
                mode=SelectSelectorMode.LIST,
            )
        )
        notify_default = (
            current_notify_services if current_notify_services else notify_services[:1]
        )
    else:
        notify_selector = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
        notify_default = (
            ", ".join(current_notify_services)
            if current_notify_services
            else "notify.mobile_app_mein_handy"
        )

    return vol.Schema(
        {
            vol.Required(CONF_USER_NAME, default=current_user_name): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Required(CONF_BRING_LIST, default=bring_default): bring_selector,
            vol.Required(CONF_NOTIFY_SERVICES, default=notify_default): notify_selector,
        }
    )

def _parse_notify(raw: Any) -> list[str]:
    """Notify-Eingabe normalisieren."""
    if isinstance(raw, str):
        return [s.strip() for s in raw.split(",") if s.strip()]
    return [s for s in list(raw) if s.strip()]

def _validate_bring_list(hass: HomeAssistant, entity_id: str) -> bool:
    """Prüft ob die Todo-Entity existiert."""
    return hass.states.get(entity_id) is not None and entity_id.startswith("todo.")

async def _get_webhook_urls(
    hass: HomeAssistant, webhook_id: str, existing_cloudhook_url: str | None = None
) -> tuple[str, str | None]:
    """Lokale URL und ggf. Nabu-Casa-URL ermitteln.

    existing_cloudhook_url: bereits gespeicherte Cloud-URL (aus entry.data).
    Falls vorhanden, wird diese direkt zurückgegeben ohne API-Aufruf.
    """
    # Lokale URL – immer über async_generate_url
    local_url = async_generate_url(hass, webhook_id)

    # Cloud-URL: vorhandene nutzen oder neu anlegen
    cloud_url: str | None = existing_cloudhook_url

    if not cloud_url:
        try:
            if async_active_subscription(hass):
                # async_get_or_create_cloudhook legt Hook an und aktiviert ihn
                cloud_url = await cloud.async_get_or_create_cloudhook(hass, webhook_id)
        except (CloudNotAvailable, AttributeError, Exception):
            cloud_url = None

    return local_url, cloud_url

def _format_webhook_info(local_url: str, cloud_url: str | None) -> str:
    """URL-Info für den Dialog formatieren."""
    if cloud_url:
        return (
            "**Lokal (nur im Heimnetz):**\n"
            f"`{local_url}`\n\n"
            "**Nabu Casa (überall erreichbar):**\n"
            f"`{cloud_url}`"
        )
    return f"`{local_url}`"

# ──────────────────────────────────────────────────────────────────────────────
# Config Flow
# ──────────────────────────────────────────────────────────────────────────────

class BarcodeBringConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow für Barcode → Bring!."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Schritt 1: Benutzername, Bring!-Liste und Notify-Dienste abfragen."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_name = user_input[CONF_USER_NAME].strip()
            bring_list = user_input[CONF_BRING_LIST]
            if isinstance(bring_list, str):
                bring_list = bring_list.strip()
            notify_services = _parse_notify(user_input[CONF_NOTIFY_SERVICES])

            await self.async_set_unique_id(f"{DOMAIN}_{user_name.lower()}")
            self._abort_if_unique_id_configured()

            if not _validate_bring_list(self.hass, bring_list):
                errors[CONF_BRING_LIST] = "invalid_bring_list"
            elif not notify_services:
                errors[CONF_NOTIFY_SERVICES] = "invalid_notify"
            else:
                self._data = {
                    CONF_USER_NAME: user_name,
                    CONF_BRING_LIST: bring_list,
                    CONF_NOTIFY_SERVICES: notify_services,
                    CONF_WEBHOOK_ID: f"barcode_bring_{secrets.token_hex(8)}",
                }
                return await self.async_step_url()

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(
                _get_todo_entities(self.hass),
                _get_notify_services(self.hass),
            ),
            errors=errors,
        )

    async def async_step_url(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Schritt 2: Cloud-Hook anlegen, URL anzeigen, Entry erstellen.

        user_input=None  → erster Aufruf, Formular anzeigen
        user_input={}    → Nutzer hat bestätigt, Entry anlegen

        Wichtig: kein internes Flag nötig – HA unterscheidet über user_input.
        """
        if user_input is not None:
            # Nutzer hat bestätigt → Entry anlegen
            user_name: str = self._data[CONF_USER_NAME]
            return self.async_create_entry(
                title=f"Barcode → Bring! ({user_name})",
                data=self._data,
            )

        # Erster Aufruf: Cloud-Hook anlegen und URL anzeigen
        webhook_id: str = self._data[CONF_WEBHOOK_ID]

        local_url, cloud_url = await _get_webhook_urls(self.hass, webhook_id)

        # Cloud-URL in _data speichern → landet in entry.data
        if cloud_url:
            self._data[CONF_CLOUDHOOK_URL] = cloud_url

        return self.async_show_form(
            step_id="url",
            data_schema=vol.Schema({}),
            description_placeholders={
                "webhook_url": _format_webhook_info(local_url, cloud_url),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Options Flow bereitstellen."""
        return BarcodeBringOptionsFlow()

# ──────────────────────────────────────────────────────────────────────────────
# Options Flow
# Regeln:
#   - Kein __init__, kein self.config_entry = ... (AttributeError seit HA 2025.12)
#   - OptionsFlowWithReload: automatischer Reload nach Änderung
#   - self.config_entry ist read-only Property – nur lesend verwenden
# ──────────────────────────────────────────────────────────────────────────────

class BarcodeBringOptionsFlow(config_entries.OptionsFlowWithReload):
    """Options Flow – bestehende Konfiguration ändern.

    Kein __init__ – würde AttributeError seit HA 2025.12 verursachen.
    Instanzvariablen werden lazy über getattr initialisiert.
    """

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Schritt 1: Einstellungen anzeigen und speichern."""
        errors: dict[str, str] = {}

        current_user_name: str = self.config_entry.data.get(CONF_USER_NAME, "")
        current_bring_list: str = self.config_entry.data.get(CONF_BRING_LIST, "")
        current_notify = self.config_entry.data.get(CONF_NOTIFY_SERVICES, [])
        if isinstance(current_notify, str):
            current_notify = [current_notify]

        if user_input is not None:
            new_user_name = user_input[CONF_USER_NAME].strip()
            new_bring_list = user_input[CONF_BRING_LIST]
            if isinstance(new_bring_list, str):
                new_bring_list = new_bring_list.strip()
            new_notify = _parse_notify(user_input[CONF_NOTIFY_SERVICES])

            if not _validate_bring_list(self.hass, new_bring_list):
                errors[CONF_BRING_LIST] = "invalid_bring_list"
            elif not new_notify:
                errors[CONF_NOTIFY_SERVICES] = "invalid_notify"
            else:
                # Neue Daten merken, dann URL anzeigen
                self._new_data: dict = dict(self.config_entry.data)
                self._new_data[CONF_USER_NAME] = new_user_name
                self._new_data[CONF_BRING_LIST] = new_bring_list
                self._new_data[CONF_NOTIFY_SERVICES] = new_notify
                return await self.async_step_url()

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(
                _get_todo_entities(self.hass),
                _get_notify_services(self.hass),
                current_user_name=current_user_name,
                current_bring_list=current_bring_list,
                current_notify_services=list(current_notify),
            ),
            errors=errors,
        )

    async def async_step_url(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Schritt 2: Webhook-URL anzeigen, dann speichern.

        user_input=None → Formular anzeigen
        user_input={}   → Nutzer hat bestätigt, speichern
        """
        if user_input is not None:
            # Nutzer hat bestätigt → speichern
            new_user_name: str = self._new_data[CONF_USER_NAME]
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                title=f"Barcode → Bring! ({new_user_name})",
                data=self._new_data,
            )
            return self.async_create_entry(title="", data={})

        # Erster Aufruf: URL anzeigen
        webhook_id: str = self.config_entry.data[CONF_WEBHOOK_ID]
        existing_cloud_url: str | None = self.config_entry.data.get(CONF_CLOUDHOOK_URL)

        local_url, cloud_url = await _get_webhook_urls(
            self.hass, webhook_id, existing_cloudhook_url=existing_cloud_url
        )

        return self.async_show_form(
            step_id="url",
            data_schema=vol.Schema({}),
            description_placeholders={
                "webhook_url": _format_webhook_info(local_url, cloud_url),
            },
        )
