"""Config Flow und Options Flow für Barcode → Bring! Integration."""
from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BRING_LIST,
    CONF_NOTIFY_SERVICES,
    CONF_USER_NAME,
    CONF_WEBHOOK_ID,
    DOMAIN,
)


def _validate_bring_list(hass: HomeAssistant, entity_id: str) -> bool:
    """Prüft ob die Todo-Entity existiert."""
    return hass.states.get(entity_id) is not None and entity_id.startswith("todo.")


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


def _build_options_schema(
    todo_entities: list[str],
    notify_services: list[str],
    current_user_name: str = "",
    current_bring_list: str = "",
    current_notify_services: list[str] | None = None,
) -> vol.Schema:
    """Schema für Optionen-Formular bauen (wird für Setup und Options genutzt)."""
    if current_notify_services is None:
        current_notify_services = []

    # todo-Feld
    if todo_entities:
        bring_field: Any = vol.In(todo_entities)
        bring_default = current_bring_list or todo_entities[0]
        bring_key = vol.Required(CONF_BRING_LIST, default=bring_default)
    else:
        bring_field = str
        bring_key = vol.Required(
            CONF_BRING_LIST,
            description={"suggested_value": current_bring_list or "todo.einkaufsliste"},
        )

    # notify-Feld: Multi-Select wenn Dienste vorhanden
    if notify_services:
        notify_field: Any = vol.All(
            [vol.In(notify_services)],
            vol.Length(min=1),
        )
        notify_default = current_notify_services if current_notify_services else [notify_services[0]]
        notify_key = vol.Required(CONF_NOTIFY_SERVICES, default=notify_default)
    else:
        # Freitext als kommagetrennte Liste
        notify_field = str
        notify_key = vol.Required(
            CONF_NOTIFY_SERVICES,
            description={"suggested_value": ", ".join(current_notify_services) if current_notify_services else "notify.mobile_app_mein_handy"},
        )

    return vol.Schema(
        {
            vol.Required(
                CONF_USER_NAME,
                default=current_user_name,
            ): str,
            bring_key: bring_field,
            notify_key: notify_field,
        }
    )


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
            bring_list = user_input[CONF_BRING_LIST].strip() if isinstance(user_input[CONF_BRING_LIST], str) else user_input[CONF_BRING_LIST]
            notify_raw = user_input[CONF_NOTIFY_SERVICES]

            # Freitext-Eingabe (kommagetrennt) → Liste
            if isinstance(notify_raw, str):
                notify_services = [s.strip() for s in notify_raw.split(",") if s.strip()]
            else:
                notify_services = list(notify_raw)

            # Unique ID pro Benutzer
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
            data_schema=_build_options_schema(
                _get_todo_entities(self.hass),
                _get_notify_services(self.hass),
            ),
            errors=errors,
        )

    async def async_step_webhook(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Schritt 2: Hinweis zur Webhook-Aktivierung in HA anzeigen."""
        if self._webhook_shown:
            user_name: str = self._data[CONF_USER_NAME]
            return self.async_create_entry(
                title=f"Barcode → Bring! ({user_name})",
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

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Options Flow bereitstellen."""
        return BarcodeBringOptionsFlow(config_entry)


class BarcodeBringOptionsFlow(config_entries.OptionsFlow):
    """Options Flow – bestehende Konfiguration ändern."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Einstellungen anzeigen und ändern."""
        errors: dict[str, str] = {}

        todo_entities = _get_todo_entities(self.hass)
        notify_services = _get_notify_services(self.hass)

        # Aktuelle Werte aus entry.data lesen
        current_user_name: str = self._entry.data.get(CONF_USER_NAME, "")
        current_bring_list: str = self._entry.data.get(CONF_BRING_LIST, "")
        # Rückwärtskompatibel: alter Einzelwert-String → Liste
        current_notify = self._entry.data.get(CONF_NOTIFY_SERVICES, [])
        if isinstance(current_notify, str):
            current_notify = [current_notify]

        if user_input is not None:
            new_user_name = user_input[CONF_USER_NAME].strip()
            new_bring_list = user_input[CONF_BRING_LIST].strip() if isinstance(user_input[CONF_BRING_LIST], str) else user_input[CONF_BRING_LIST]
            notify_raw = user_input[CONF_NOTIFY_SERVICES]

            if isinstance(notify_raw, str):
                new_notify = [s.strip() for s in notify_raw.split(",") if s.strip()]
            else:
                new_notify = list(notify_raw)

            if not _validate_bring_list(self.hass, new_bring_list):
                errors[CONF_BRING_LIST] = "invalid_bring_list"
            elif not new_notify:
                errors[CONF_NOTIFY_SERVICES] = "invalid_notify"
            else:
                # Webhook-ID bleibt erhalten – nur die änderbaren Felder updaten
                new_data = dict(self._entry.data)
                new_data[CONF_USER_NAME] = new_user_name
                new_data[CONF_BRING_LIST] = new_bring_list
                new_data[CONF_NOTIFY_SERVICES] = new_notify

                # entry.data aktualisieren und Titel anpassen
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    title=f"Barcode → Bring! ({new_user_name})",
                    data=new_data,
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_build_options_schema(
                todo_entities,
                notify_services,
                current_user_name=current_user_name,
                current_bring_list=current_bring_list,
                current_notify_services=current_notify,
            ),
            errors=errors,
        )
