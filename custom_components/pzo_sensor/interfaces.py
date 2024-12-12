"""Interfacce di gestione di pzo_sensor."""

from enum import Enum

class Fascia(Enum):
    """Enumerazione con i tipi di fascia oraria."""

    MONO = "MONO"
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F23 = "F23"
    ORARIA = "ORARIA"


class PricesData:
    """Classe che contiene i valori del prezzi orari per ciascuna fascia."""

    def __init__(self):
        self.data: dict[Fascia, list[float]] = {
            Fascia.ORARIA: [0] * 24,
            Fascia.F1: [0] * 24,
            Fascia.F2: [0] * 24,
            Fascia.F3: [0] * 24,
            Fascia.F23: [0] * 24,
        }


class PricesValues:
    """Classe che contiene il prezzi attuale di ciascuna fascia."""

    value: dict[Fascia, float] = {
        Fascia.MONO: 0.0,
        Fascia.F1: 0.0,
        Fascia.F2: 0.0,
        Fascia.F3: 0.0,
        Fascia.F23: 0.0,
        Fascia.ORARIA: 0.0
    }