"""Config Flow und Options Flow für Barcode → Bring! Integration."""
from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.webhook import async_generate_url
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.network import NoURLAvailableError, get_url
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
    """Schema mit HA-Selektoren bauen (korrekte UI-Darstellung)."""
    if current_notify_services is None:
        current_notify_services = []

    # Bring!-Liste: Dropdown-Selektor wenn Entities vorhanden
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

    # Notify-Dienste: Multi-Select-Selektor wenn Dienste vorhanden
    if notify_services:
        notify_selector = SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=s, label=s) for s in notify_services],
                multiple=True,
                mode=SelectSelectorMode.LIST,
            )
        )
        notify_default = current_notify_services if current_notify_services else notify_services[:1]
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
    """Notify-Eingabe normalisieren (Liste oder kommagetrennte Zeichenkette)."""
    if isinstance(raw, str):
        return [s.strip() for s in raw.split(",") if s.strip()]
    return [s for s in list(raw) if s.strip()]

def _validate_bring_list(hass: HomeAssistant, entity_id: str) -> bool:
    """Prüft ob die Todo-Entity existiert."""
    return hass.states.get(entity_id) is not None and entity_id.startswith("todo.")

# ──────────────────────────────────────────────────────────────────────────────
# Config Flow
# ──────────────────────────────────────────────────────────────────────────────

class BarcodeBringConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow für Barcode → Bring!."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}
        # Steuert ob Schritt 2 bereits angezeigt wurde.
        # Nötig weil HA bei vol.Schema({}) user_input={} übergibt, nicht None.
        self._webhook_shown = False

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

            # Unique ID pro Benutzer – verhindert Dopplungen
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
                return await self.async_step_webhook()

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(
                _get_todo_entities(self.hass),
                _get_notify_services(self.hass),
            ),
            errors=errors,
        )

    async def async_step_webhook(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Schritt 2: Fertige Webhook-URL(s) anzeigen."""
        if self._webhook_shown:
            user_name: str = self._data[CONF_USER_NAME]
            return self.async_create_entry(
                title=f"Barcode → Bring! ({user_name})",
                data=self._data,
            )

        self._webhook_shown = True
        webhook_id: str = self._data[CONF_WEBHOOK_ID]

        # Lokale URL – immer verfügbar
        local_url = async_generate_url(self.hass, webhook_id)

        # Nabu Casa Cloud-URL:
        # async_create_cloudhook läuft in async_setup_entry – hier nur anzeigen
        cloud_url: str | None = None
        try:
            external = get_url(
                self.hass,
                allow_internal=False,
                allow_ip=False,
                prefer_cloud=True,
            )
            cloud_url = f"{external}/api/webhook/{webhook_id}"
        except NoURLAvailableError:
            pass

        if cloud_url:
            webhook_info = (
                "**Lokal (nur im Heimnetz):**\n"
                f"`{local_url}`\n\n"
                "**Nabu Casa (überall erreichbar, wird automatisch aktiviert):**\n"
                f"`{cloud_url}`"
            )
        else:
            webhook_info = f"`{local_url}`"

        return self.async_show_form(
            step_id="webhook",
            data_schema=vol.Schema({}),
            description_placeholders={
                "webhook_url": webhook_info,
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
#   - OptionsFlowWithReload: automatischer Reload nach Änderung, kein update_listener nötig
#   - self.config_entry ist read-only Property – nur lesend verwenden
# ──────────────────────────────────────────────────────────────────────────────

class BarcodeBringOptionsFlow(config_entries.OptionsFlowWithReload):
    """Options Flow – bestehende Konfiguration ändern."""

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Einstellungen anzeigen und speichern."""
        errors: dict[str, str] = {}

        current_user_name: str = self.config_entry.data.get(CONF_USER_NAME, "")
        current_bring_list: str = self.config_entry.data.get(CONF_BRING_LIST, "")
        current_notify = self.config_entry.data.get(CONF_NOTIFY_SERVICES, [])
        if isinstance(current_notify, str):
            current_notify = [current_notify]

        todo_entities = _get_todo_entities(self.hass)
        notify_services = _get_notify_services(self.hass)

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
                new_data = dict(self.config_entry.data)
                new_data[CONF_USER_NAME] = new_user_name
                new_data[CONF_BRING_LIST] = new_bring_list
                new_data[CONF_NOTIFY_SERVICES] = new_notify

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=f"Barcode → Bring! ({new_user_name})",
                    data=new_data,
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(
                todo_entities,
                notify_services,
                current_user_name=current_user_name,
                current_bring_list=current_bring_list,
                current_notify_services=list(current_notify),
            ),
            errors=errors,
        )
