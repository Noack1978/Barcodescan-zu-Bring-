"""Config Flow für Barcode → Bring! Integration."""
from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .const import CONF_BRING_LIST, CONF_NOTIFY_SERVICE, CONF_WEBHOOK_ID, DOMAIN


def _validate_bring_list(hass: HomeAssistant, entity_id: str) -> bool:
    """Prüft ob die Todo-Entity existiert."""
    return hass.states.get(entity_id) is not None and entity_id.startswith("todo.")


def _validate_notify(hass: HomeAssistant, service: str) -> bool:
    """Prüft ob der Notify-Dienst das richtige Format hat.

    hass.services.has_service() gibt für Companion-App-Dienste (notify.mobile_app_*)
    False zurück, weil diese lazy registriert werden. Daher wird nur das Format
    geprüft – ein falsch eingetragener Dienst zeigt sich beim ersten Scan im Log.
    """
    if not service.startswith("notify."):
        return False
    parts = service.split(".", 1)
    return len(parts) == 2 and bool(parts[1].strip())




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
        """Schritt 1: Bring!-Liste und Notify-Dienst abfragen."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}

        if user_input is not None:
            bring_list = user_input[CONF_BRING_LIST].strip()
            notify_service = user_input[CONF_NOTIFY_SERVICE].strip()

            if not _validate_bring_list(self.hass, bring_list):
                errors[CONF_BRING_LIST] = "invalid_bring_list"
            elif not _validate_notify(self.hass, notify_service):
                errors[CONF_NOTIFY_SERVICE] = "invalid_notify"
            else:
                self._data = {
                    CONF_BRING_LIST: bring_list,
                    CONF_NOTIFY_SERVICE: notify_service,
                    CONF_WEBHOOK_ID: f"barcode_bring_{secrets.token_hex(8)}",
                }
                return await self.async_step_webhook()

        # Alle vorhandenen todo-Entities fuer Dropdown ermitteln
        todo_entities = sorted(
            state.entity_id
            for state in self.hass.states.async_all()
            if state.entity_id.startswith("todo.")
        )

        # Alle vorhandenen notify-Dienste fuer Dropdown ermitteln
        notify_services = sorted(
            f"notify.{name}"
            for name in (self.hass.services.async_services().get("notify") or {})
            if name not in ("send_message", "notify", "persistent_notification")
        )

        # Schema: Dropdown wenn Optionen vorhanden, sonst Freitext
        if todo_entities:
            bring_field: Any = vol.In(todo_entities)
            bring_key = vol.Required(CONF_BRING_LIST, default=todo_entities[0])
        else:
            bring_field = str
            bring_key = vol.Required(
                CONF_BRING_LIST,
                description={"suggested_value": "todo.einkaufsliste"},
            )

        if notify_services:
            notify_field: Any = vol.In(notify_services)
            notify_key = vol.Required(CONF_NOTIFY_SERVICE, default=notify_services[0])
        else:
            notify_field = str
            notify_key = vol.Required(
                CONF_NOTIFY_SERVICE,
                description={"suggested_value": "notify.mobile_app_mein_handy"},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({bring_key: bring_field, notify_key: notify_field}),
            errors=errors,
        )

    async def async_step_webhook(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Schritt 2: Hinweis zur Webhook-Aktivierung in HA anzeigen."""
        if self._webhook_shown:
            return self.async_create_entry(
                title="Barcode → Bring!",
                data=self._data,
            )

        self._webhook_shown = True
        webhook_id: str = self._data[CONF_WEBHOOK_ID]

        return self.async_show_form(
            step_id="webhook",
            data_schema=vol.Schema({}),
            description_placeholders={
                "webhook_id": webhook_id,
            },
        )
