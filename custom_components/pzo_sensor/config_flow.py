"""UI di configurazione per pzo_sensor."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_ACTUAL_DATA_ONLY, CONF_SCAN_HOUR, CONF_ZONE, DEFAULT_ZONE, CONF_CONTRACT, DEFAULT_CONTRACT, CONF_MONTH_AVG, ZONE_CODES, CONTRACTS, DOMAIN


class OptionsFlow(config_entries.OptionsFlow):
    """Opzioni per prezzi zonali (= riconfigurazione successiva)."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Inizializzazione opzioni."""
        self.config_entry = entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Gestisce le opzioni."""
        errors: dict[str, str] | None = {}
        if user_input is not None:
            # Configurazione valida (validazione integrata nello schema)
            return self.async_create_entry(title="Prezzi Zonali", data=user_input)

        # Schema dati di opzione (con default sui valori attuali)
        data_schema = {
            vol.Required(
                CONF_ZONE,
                default=self.config_entry.options.get(
                    CONF_ZONE, self.config_entry.data[CONF_ZONE]
                )
            ): vol.In(ZONE_CODES.keys()),
            vol.Required(
                CONF_CONTRACT,
                default=self.config_entry.options.get(
                    CONF_CONTRACT, self.config_entry.data[CONF_CONTRACT]
                )
            ): vol.In(CONTRACTS.keys()),
            vol.Required(
                CONF_SCAN_HOUR,
                default=self.config_entry.options.get(
                    CONF_SCAN_HOUR, self.config_entry.data[CONF_SCAN_HOUR]
                ),
            ): vol.All(cv.positive_int, vol.Range(min=0, max=23)),
            vol.Optional(
                CONF_MONTH_AVG,
                default=self.config_entry.options.get(
                    CONF_MONTH_AVG, self.config_entry.data[CONF_MONTH_AVG]
                ),
            ): cv.boolean,
            vol.Optional(
                CONF_ACTUAL_DATA_ONLY,
                default=self.config_entry.options.get(
                    CONF_ACTUAL_DATA_ONLY, self.config_entry.data[CONF_ACTUAL_DATA_ONLY]
                ),
            ): cv.boolean,
        }

        # Mostra la schermata di configurazione, con gli eventuali errori
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(data_schema), errors=errors
        )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configurazione per prezzi zonali (= prima configurazione)."""

    # Versione della configurazione (per utilizzi futuri)
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlow:
        """Ottiene le opzioni per questa configurazione."""
        return OptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Gestione prima configurazione da Home Assistant."""
        # Controlla che l'integrazione non venga eseguita più volte
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors = {}
        if user_input is not None:
            # Configurazione valida (validazione integrata nello schema)
            return self.async_create_entry(title="Prezzi Zonali", data=user_input)

        # Schema dati di configurazione (con default fissi)
        data_schema = {
            vol.Required(CONF_ZONE, default=DEFAULT_ZONE): vol.In(ZONE_CODES.keys()),
            vol.Required(CONF_CONTRACT, default=DEFAULT_CONTRACT): vol.In(CONTRACTS.keys()),
            vol.Required(CONF_SCAN_HOUR, default=1): vol.All(
                cv.positive_int, vol.Range(min=0, max=23)
            ),
            vol.Optional(CONF_MONTH_AVG, default=True): cv.boolean,
            vol.Optional(CONF_ACTUAL_DATA_ONLY, default=False): cv.boolean,
        }

        # Mostra la schermata di configurazione, con gli eventuali errori
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors
        )
