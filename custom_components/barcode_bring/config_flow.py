"""Config Flow und Options Flow für Barcode → Bring! Integration."""
from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
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

def _build_url_info(local_url: str, has_nabu_casa: bool) -> str:
    """URL-Info-Text für den Dialog bauen.

    Die Nabu-Casa-URL ist erst nach async_setup_entry bekannt.
    Wir zeigen die lokale URL und einen Hinweis falls Nabu Casa aktiv ist.
    """
    if has_nabu_casa:
        return (
            f"Lokale URL (Heimnetz): {local_url}\n\n"
            "Nabu Casa URL: wird nach Abschluss unter "
            "Einstellungen → Home Assistant Cloud → Webhooks angezeigt."
        )
    return f"Lokale URL: {local_url}"

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
        """Schritt 2: Webhook-URL anzeigen.

        user_input=None → Formular anzeigen
        user_input={}   → Entry anlegen
        """
        if user_input is not None:
            user_name: str = self._data[CONF_USER_NAME]
            return self.async_create_entry(
                title=f"Barcode → Bring! ({user_name})",
                data=self._data,
            )

        webhook_id: str = self._data[CONF_WEBHOOK_ID]
        local_url = async_generate_url(self.hass, webhook_id)

        # Nabu Casa aktiv?
        has_nabu_casa = False
        try:
            from homeassistant.components.cloud import async_active_subscription
            has_nabu_casa = async_active_subscription(self.hass)
        except Exception:
            pass

        return self.async_show_form(
            step_id="url",
            data_schema=vol.Schema({}),
            description_placeholders={
                "local_url": local_url,
                "nabu_hint": (
                    "Nabu Casa URL: Einstellungen → Home Assistant Cloud → Webhooks → Webhook aktivieren → URL kopieren.\n\n"
                    if has_nabu_casa else ""
                ),
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
#   - Kein __init__ (AttributeError seit HA 2025.12)
#   - OptionsFlowWithReload: automatischer Reload nach Änderung
#   - self.config_entry ist read-only Property – nur lesend verwenden
# ──────────────────────────────────────────────────────────────────────────────

class BarcodeBringOptionsFlow(config_entries.OptionsFlowWithReload):
    """Options Flow – bestehende Konfiguration ändern."""

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
        """Webhook-URL anzeigen (aus Konfigurieren heraus aufrufbar)."""
        if user_input is not None:
            return self.async_create_entry(title="", data={})

        webhook_id: str = self.config_entry.data[CONF_WEBHOOK_ID]
        local_url = async_generate_url(self.hass, webhook_id)
        cloud_url: str | None = self.config_entry.data.get(CONF_CLOUDHOOK_URL)

        has_nabu_casa = bool(cloud_url)

        return self.async_show_form(
            step_id="url",
            data_schema=vol.Schema({}),
            description_placeholders={
                "local_url": local_url,
                "nabu_hint": (
                    f"Nabu Casa URL: {cloud_url}"
                    if has_nabu_casa else ""
                ),
            },
        )
