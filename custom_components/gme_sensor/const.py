"""Costanti utilizzate da gme_sensor."""

# Dominio HomeAssistant
DOMAIN = "gme_sensor"

# Intervalli di tempo per i tentativi
WEB_RETRIES_MINUTES = [1, 10, 60, 120, 180]

# Tipi di aggiornamento
COORD_EVENT = "coordinator_event"
EVENT_UPDATE_FASCIA = "event_update_fascia"
EVENT_UPDATE_PREZZI = "event_update_prezzi"
EVENT_UPDATE_ORARIO = "event_update_orario"

# Parametri configurabili da configuration.yaml
CONF_ZONE = "zone"
CONF_SCAN_HOUR = "scan_hour"
CONF_ACTUAL_DATA_ONLY = "actual_data_only"

# Parametri interni
CONF_SCAN_MINUTE = "scan_minute"

# Traduce i nomi delle zone nei rispettivi codici presenti nell'xml
ZONE_CODES = {
    "Austria": "AUST",
    "Slovenia Coupling": "BSP",
    "Calabria": "CALA",
    "Centro Nord": "CNOR",
    "Corsica AC": "COAC",
    "Corsica": "CORS",
    "Italia Coupling": "COUP",
    "Centro Sud": "CSUD",
    "Francia": "FRAN",
    "Grecia": "GREC",
    "Malta": "MALT",
    "Montenegro": "MONT",
    "Italia (senza vincoli)": "NAT",
    "Nord": "NORD",
    "Sardegna": "SARD",
    "Sicilia": "SICI",
    "Slovenia": "SLOV",
    "Sud": "SUD",
    "Svizzera": "SVIZ",
    "Austria Coupling": "XAUS",
    "Francia Coupling": "XFRA",
    "Grecia Coupling": "XGRE",
}