"""Prezzi zonali del mese."""

from datetime import timedelta
import logging

from awesomeversion.awesomeversion import AwesomeVersion
from holidays import country_holidays

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later, async_track_point_in_time
import homeassistant.util.dt as dt_util

from .const import CONF_ACTUAL_DATA_ONLY, CONF_SCAN_HOUR, ZONE_CODES, CONF_ZONE, CONTRACTS, CONF_CONTRACT, CONF_MONTH_AVG, DOMAIN, WEB_RETRIES_MINUTES
from .coordinator import PricesDataUpdateCoordinator

if AwesomeVersion(HA_VERSION) >= AwesomeVersion("2024.5.0"):
    from homeassistant.setup import SetupPhases, async_pause_setup

# Ottiene il logger
_LOGGER = logging.getLogger(__name__)

# Definisce i tipi di entità
PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Impostazione dell'integrazione da configurazione Home Assistant."""

    # Carica le dipendenze di holidays in background per evitare errori nel log
    if AwesomeVersion(HA_VERSION) >= AwesomeVersion("2024.5.0"):
        with async_pause_setup(hass, SetupPhases.WAIT_IMPORT_PACKAGES):
            await hass.async_add_import_executor_job(country_holidays, "IT")

    # Salva il coordinator nella configurazione
    coordinator = PricesDataUpdateCoordinator(hass, config)
    hass.data.setdefault(DOMAIN, {})[config.entry_id] = coordinator

    # Aggiorna immedianamente l'orario corrente
    await coordinator.update_orario()

    # Aggiorna immediatamente la fascia oraria corrente
    await coordinator.update_fascia()

    # Crea i sensori con la configurazione specificata
    await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)

    # Schedula l'aggiornamento via web 10 secondi dopo l'avvio
    coordinator.schedule_token = async_call_later(
        hass, timedelta(seconds=10), coordinator.update_prezzi
    )

    # Registra il callback di modifica opzioni
    config.async_on_unload(config.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Rimozione dell'integrazione da Home Assistant."""

    # Scarica i sensori (disabilitando di conseguenza il coordinator)
    unload_ok = await hass.config_entries.async_unload_platforms(config, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(config.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, config: ConfigEntry) -> None:
    """Modificate le opzioni da Home Assistant."""
    reload = False

    # Recupera il coordinator
    coordinator = hass.data[DOMAIN][config.entry_id]

    # Aggiorna le impostazioni del coordinator dalle opzioni
    if (CONF_ZONE in config.options) and (
        config.options[CONF_ZONE] != coordinator.zone
    ):
        # Modificata la zona geografica nelle opzioni
        coordinator.zone = ZONE_CODES[config.options[CONF_ZONE]]
        reload = True

    if (CONF_CONTRACT in config.options) and (
        config.options[CONF_CONTRACT] != coordinator.contract
    ):
        # Modificata il tipo di contratto nelle opzioni
        coordinator.contract = CONTRACTS[config.options[CONF_CONTRACT]]
        reload = True

    if (CONF_SCAN_HOUR in config.options) and (
        config.options[CONF_SCAN_HOUR] != coordinator.scan_hour
    ):
        # Modificata l'ora di scansione nelle opzioni
        coordinator.scan_hour = config.options[CONF_SCAN_HOUR]

        # Rigenera il minuto di esecuzione
        coordinator.update_scan_minutes_from_config(
            hass=hass, config=config, new_minute=True
        )

        # Calcola la data della prossima esecuzione (all'ora definita)
        now = dt_util.now()
        next_update = now.replace(
            hour=coordinator.scan_hour,
            minute=coordinator.scan_minute,
            second=0,
            microsecond=0,
        )
        if next_update <= now:
            # Se l'evento è già trascorso, passa a domani alla stessa ora
            next_update = next_update + timedelta(days=1)

        # Annulla eventuali schedulazioni attive
        if coordinator.schedule_token is not None:
            coordinator.schedule_token()
            coordinator.schedule_token = None

        # Schedula la prossima esecuzione
        coordinator.web_retries = WEB_RETRIES_MINUTES
        coordinator.schedule_token = async_track_point_in_time(
            coordinator.hass, coordinator.update_prezzi, next_update
        )
        _LOGGER.debug(
            "Prossimo aggiornamento web: %s",
            next_update.strftime("%d/%m/%Y %H:%M:%S %z"),
        )

    if (CONF_ACTUAL_DATA_ONLY in config.options) and (
        config.options[CONF_ACTUAL_DATA_ONLY] != coordinator.actual_data_only
    ):
        # Modificata impostazione 'Usa dati reali'
        coordinator.actual_data_only = config.options[CONF_ACTUAL_DATA_ONLY]
        _LOGGER.debug(
            "Nuovo valore 'usa dati reali': %s.", coordinator.actual_data_only
        )
        reload = True

        # Annulla eventuali schedulazioni attive
        if coordinator.schedule_token is not None:
            coordinator.schedule_token()
            coordinator.schedule_token = None
    
    if (CONF_MONTH_AVG in config.options) and (
        config.options[CONF_MONTH_AVG] != coordinator.month_average
    ):
        # Modificata il metodo di calcolo dei prezzi nelle opzioni
        coordinator.month_average = config.options[CONF_MONTH_AVG]
        reload = True

    if (reload):
        # Esegue un nuovo aggiornamento immediatamente
        coordinator.web_retries = WEB_RETRIES_MINUTES
        coordinator.schedule_token = async_call_later(
            coordinator.hass, timedelta(seconds=5), coordinator.update_prezzi
        )
