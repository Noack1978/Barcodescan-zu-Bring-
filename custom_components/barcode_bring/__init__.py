"""Barcode → Bring! Integration für Home Assistant."""
from __future__ import annotations

import asyncio
import dataclasses
import logging
import re
import time
from typing import Any
from typing import TypeAlias

import aiohttp
from homeassistant.components import cloud
from homeassistant.components.cloud import CloudNotAvailable
from homeassistant.components.webhook import (
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    API_OPENBEAUTY,
    API_OPENFOOD,
    API_OPENPRODUCTS,
    CONF_BRING_LIST,
    CONF_CLOUDHOOK_URL,
    CONF_NOTIFY_SERVICES,
    CONF_SUCCESS_NOTIFY,
    CONF_USER_NAME,
    CONF_WEBHOOK_ID,
    DOMAIN,
    UNKNOWN_VALUES,
)

_LOGGER = logging.getLogger(__name__)

@dataclasses.dataclass
class BarcodeBringData:
    """Laufzeitdaten der Integration – gespeichert in entry.runtime_data."""

    queue: asyncio.Queue[str]
    worker: asyncio.Task[None]
    queued_barcodes: set[str]

BarcodeBringConfigEntry: TypeAlias = ConfigEntry[BarcodeBringData]

async def async_setup_entry(hass: HomeAssistant, entry: BarcodeBringConfigEntry) -> bool:
    """Integration einrichten."""
    webhook_id: str = entry.data[CONF_WEBHOOK_ID]
    user_name: str = entry.data.get(CONF_USER_NAME, "Unbekannt")

    queue: asyncio.Queue[str] = asyncio.Queue()
    queued_barcodes: set[str] = set()

    # Background Task – nicht als tracked task registrieren, da er ewig läuft
    # async_create_task() würde den HA-Bootstrap blockieren
    worker_task = hass.async_create_background_task(
        _barcode_worker(hass, entry, queue, queued_barcodes),
        name=f"barcode_bring_worker_{webhook_id}",
    )

    entry.runtime_data = BarcodeBringData(
        queue=queue,
        worker=worker_task,
        queued_barcodes=queued_barcodes,
    )

    webhook_register(
        hass,
        DOMAIN,
        f"Barcode Scan ({user_name})",
        webhook_id,
        _handle_webhook,
        allowed_methods=["POST"],
        local_only=False,
    )

    _LOGGER.info("Barcode → Bring! (%s): Webhook '%s' registriert", user_name, webhook_id)

    return True

async def async_remove_entry(hass: HomeAssistant, entry: BarcodeBringConfigEntry) -> None:
    """Cloud-Hook beim Entfernen der Integration löschen."""
    if CONF_CLOUDHOOK_URL in entry.data:
        try:
            await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
        except (CloudNotAvailable, ValueError):
            pass

async def async_unload_entry(hass: HomeAssistant, entry: BarcodeBringConfigEntry) -> bool:
    """Integration entladen."""
    webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    data: BarcodeBringData = entry.runtime_data
    if not data.worker.done():
        data.worker.cancel()
        try:
            await data.worker
        except asyncio.CancelledError:
            pass

    _LOGGER.info("Barcode → Bring!: Integration entladen")
    return True

# ──────────────────────────────────────────────────────────────────────────────
# Webhook-Handler
# ──────────────────────────────────────────────────────────────────────────────

async def _handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: Any
) -> None:
    """Barcode empfangen und in die Verarbeitungs-Queue legen."""
    try:
        body = await request.json()
    except Exception:
        _LOGGER.warning("Barcode → Bring!: Ungültiger JSON-Body im Webhook")
        return

    barcode = str(body.get("content", "")).strip()
    if not barcode:
        _LOGGER.warning("Barcode → Bring!: Leerer Barcode empfangen")
        return

    # Entry über webhook_id ermitteln
    entry: BarcodeBringConfigEntry | None = next(
        (
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.data.get(CONF_WEBHOOK_ID) == webhook_id
        ),
        None,
    )
    if entry is None:
        _LOGGER.error("Barcode → Bring!: Kein Entry für Webhook '%s' gefunden", webhook_id)
        return

    # runtime_data sicher prüfen – ist nach setup_entry immer gesetzt
    try:
        data: BarcodeBringData = entry.runtime_data
    except AttributeError:
        _LOGGER.error("Barcode → Bring!: Integration nicht vollständig geladen")
        return

    if barcode in data.queued_barcodes:
        _LOGGER.debug("Barcode → Bring!: '%s' bereits in Queue, übersprungen", barcode)
        return

    data.queued_barcodes.add(barcode)
    await data.queue.put(barcode)
    _LOGGER.debug(
        "Barcode → Bring!: '%s' in Queue (%d wartend)", barcode, data.queue.qsize()
    )

# ──────────────────────────────────────────────────────────────────────────────
# Worker
# ──────────────────────────────────────────────────────────────────────────────

async def _barcode_worker(
    hass: HomeAssistant,
    entry: BarcodeBringConfigEntry,
    queue: asyncio.Queue[str],
    queued_barcodes: set[str],
) -> None:
    """Dauerhaft laufender Worker – verarbeitet Barcodes aus der Queue."""
    _LOGGER.debug("Barcode → Bring!: Worker gestartet")
    while True:
        try:
            barcode = await queue.get()
            try:
                await _process_barcode(hass, entry, barcode)
            except Exception as err:
                _LOGGER.error(
                    "Barcode → Bring!: Fehler bei Verarbeitung von '%s': %s",
                    barcode,
                    err,
                )
            finally:
                queued_barcodes.discard(barcode)
                queue.task_done()
        except asyncio.CancelledError:
            _LOGGER.debug("Barcode → Bring!: Worker beendet")
            break

# ──────────────────────────────────────────────────────────────────────────────
# Barcode verarbeiten
# ──────────────────────────────────────────────────────────────────────────────

async def _process_barcode(
    hass: HomeAssistant, entry: BarcodeBringConfigEntry, barcode: str
) -> None:
    """Einen Barcode nachschlagen und in die Bring!-Liste eintragen."""
    bring_list: str = entry.data[CONF_BRING_LIST]

    # Notify-Dienste: rückwärtskompatibel mit altem Einzelwert-String
    notify_raw = entry.data.get(CONF_NOTIFY_SERVICES, [])
    if isinstance(notify_raw, str):
        notify_services: list[str] = [notify_raw]
    else:
        notify_services = list(notify_raw)

    produktname = await _lookup_product(barcode)

    if not produktname or produktname in UNKNOWN_VALUES:
        _LOGGER.info("Barcode → Bring!: Produkt nicht gefunden für '%s'", barcode)
        for service in notify_services:
            try:
                notify_domain, notify_name = service.split(".", 1)
                await hass.services.async_call(
                    notify_domain,
                    notify_name,
                    {
                        "title": "Produkt nicht gefunden",
                        "message": f"Barcode {barcode} konnte keinem Produkt zugeordnet werden.",
                    },
                    blocking=False,
                )
            except Exception as err:
                _LOGGER.warning("Benachrichtigung an '%s' fehlgeschlagen: %s", service, err)
        return

    clean_name = re.sub(r"[–—]", "-", produktname).strip()
    user_name: str = entry.data.get(CONF_USER_NAME, "Unbekannt")
    _LOGGER.info("Barcode → Bring!: Füge '%s' zu '%s' hinzu", clean_name, bring_list)
    await hass.services.async_call(
        "todo",
        "add_item",
        {"item": clean_name},
        target={"entity_id": bring_list},
        blocking=True,
    )

    # Persistente Benachrichtigung in der HA-Seitenleiste – optional
    # Jede Benachrichtigung bleibt erhalten (eindeutige ID per Zeitstempel)
    if entry.data.get(CONF_SUCCESS_NOTIFY, True):
        notif_id = f"barcode_bring_{user_name.lower()}_{int(time.time())}"
        try:
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": f"Barcode → Bring! ({user_name})",
                    "message": f"{clean_name} wurde zur Einkaufsliste hinzugefügt.",
                    "notification_id": notif_id,
                },
                blocking=False,
            )
        except Exception as err:
            _LOGGER.warning("Persistente Benachrichtigung fehlgeschlagen: %s", err)

# ──────────────────────────────────────────────────────────────────────────────
# APIs
# ──────────────────────────────────────────────────────────────────────────────

async def _lookup_product(barcode: str) -> str | None:
    """Barcode in allen drei APIs parallel nachschlagen."""
    urls = [
        API_OPENFOOD.format(barcode),
        API_OPENBEAUTY.format(barcode),
        API_OPENPRODUCTS.format(barcode),
    ]

    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            *[_fetch_product_name(session, url) for url in urls],
            return_exceptions=True,
        )

    for result in results:
        if isinstance(result, str) and result not in UNKNOWN_VALUES:
            return result

    return None

async def _fetch_product_name(session: aiohttp.ClientSession, url: str) -> str:
    """Einen API-Endpunkt abfragen und Produktnamen extrahieren."""
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status != 200:
                return "Unbekannt"
            data = await resp.json(content_type=None)
            if data.get("status") != 1:
                return "Unbekannt"
            product = data.get("product", {})
            parts = [
                product.get("product_name", "").strip(),
                product.get("brands", "").strip(),
                product.get("quantity", "").strip(),
            ]
            joined = " – ".join(p for p in parts if p)
            return joined if joined else "Unbekannt"
    except Exception as err:
        _LOGGER.debug("API-Abfrage fehlgeschlagen (%s): %s", url, err)
        return "Unbekannt"
