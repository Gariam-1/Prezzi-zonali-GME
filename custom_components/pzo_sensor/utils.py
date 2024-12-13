"""Metodi di utilità generale."""

from datetime import date, datetime, timedelta
import logging
from zipfile import ZipFile

import defusedxml.ElementTree as et  # type: ignore[import-untyped]
import holidays

from .const import PHYSICAL_ZONES
from .interfaces import Fascia, PricesData

# Ottiene il logger
_LOGGER = logging.getLogger(__name__)


def get_fascia_for_xml(data: date, festivo: bool, ora: int) -> Fascia:
    """Restituisce la fascia oraria di un determinato giorno/ora."""
    # F1 = lu-ve 8-19
    # F2 = lu-ve 7-8, lu-ve 19-23, sa 7-23
    # F3 = lu-sa 0-7, lu-sa 23-24, do, festivi

    # Festivi e domeniche
    if festivo or (data.weekday() == 6):
        return Fascia.F3

    # Sabato
    if data.weekday() == 5:
        if 7 <= ora < 23:
            return Fascia.F2
        return Fascia.F3

    # Altri giorni della settimana
    if ora == 7 or 19 <= ora < 23:
        return Fascia.F2
    if 8 <= ora < 19:
        return Fascia.F1
    return Fascia.F3


def get_fascia(dataora: datetime) -> tuple[Fascia, datetime]:
    """Restituisce la fascia della data/ora indicata e la data del prossimo cambiamento."""

    # Verifica se la data corrente è un giorno con festività
    festivo = dataora in holidays.IT()  # type: ignore[attr-defined]

    # Identifica la fascia corrente
    # F1 = lu-ve 8-19
    # F2 = lu-ve 7-8, lu-ve 19-23, sa 7-23
    # F3 = lu-sa 0-7, lu-sa 23-24, do, festivi
    # Festivi
    if festivo:
        fascia = Fascia.F3

        # Prossima fascia: alle 7 di un giorno non domenica o festività
        prossima = get_next_date(dataora, 7, 1, True)

        return fascia, prossima
    match dataora.weekday():
        # Domenica
        case 6:
            fascia = Fascia.F3
            prossima = get_next_date(dataora, 7, 1, True)

        # Sabato
        case 5:
            if 7 <= dataora.hour < 23:
                # Sabato dalle 7 alle 23
                fascia = Fascia.F2
                # Prossima fascia: alle 23 dello stesso giorno
                prossima = get_next_date(dataora, 23)
            # abbiamo solo due fasce quindi facciamo solo il check per la prossima fascia
            else:
                # Sabato dopo le 23 e prima delle 7
                fascia = Fascia.F3

                if dataora.hour < 7:
                    # Prossima fascia: alle 7 dello stesso giorno
                    prossima = get_next_date(dataora, 7)
                else:
                    # Prossima fascia: alle 7 di un giorno non domenica o festività
                    prossima = get_next_date(dataora, 7, 1, True)

        # Altri giorni della settimana
        case _:
            if dataora.hour == 7 or 19 <= dataora.hour < 23:
                # Lunedì-venerdì dalle 7 alle 8 e dalle 19 alle 23
                fascia = Fascia.F2

                if dataora.hour == 7:
                    # Prossima fascia: alle 8 dello stesso giorno
                    prossima = get_next_date(dataora, 8)
                else:
                    # Prossima fascia: alle 23 dello stesso giorno
                    prossima = get_next_date(dataora, 23)

            elif 8 <= dataora.hour < 19:
                # Lunedì-venerdì dalle 8 alle 19
                fascia = Fascia.F1
                # Prossima fascia: alle 19 dello stesso giorno
                prossima = get_next_date(dataora, 19)

            else:
                # Lunedì-venerdì dalle 23 alle 7 del giorno dopo
                fascia = Fascia.F3

                if dataora.hour < 7:
                    # Siamo dopo la mezzanotte
                    # Prossima fascia: alle 7 dello stesso giorno
                    prossima = get_next_date(dataora, 7)
                else:
                    # Prossima fascia: alle 7 di un giorno non domenica o festività
                    prossima = get_next_date(dataora, 7, 1, True)

    return fascia, prossima


def get_next_date(
    dataora: datetime, ora: int, offset: int = 0, feriale: bool = False, minuto: int = 0
) -> datetime:
    """Ritorna una datetime in base ai parametri.

    Args:
    dataora (datetime): passa la data di riferimento.
    ora (int): l'ora a cui impostare la data.
    offset (int = 0): scostamento in giorni rispetto a dataora.
    feriale (bool = False): se True ritorna sempre una giornata lavorativa (no festivi, domeniche)
    minuto (int = 0): minuto a cui impostare la data.

    Returns:
        prossima (datetime): L'istanza di datetime corrispondente.

    """

    prossima = (dataora + timedelta(days=offset)).replace(
        hour=ora, minute=minuto, second=0, microsecond=0
    )

    if feriale:
        while (prossima in holidays.IT()) or (prossima.weekday() == 6):  # type: ignore[attr-defined]
            prossima += timedelta(days=1)

    return prossima


def extract_xml(priceArchive: ZipFile, pz_data: dict, zone: str) -> list[dict[Fascia, list[float]]]:
    """Estrae i valori dei prezzi per ogni fascia da un archivio zip contenente un XML per giorno del mese.

    Returns tuple(zonali, consumi zonali):
    List[ list[ORARIA: float], list[F1: float], list[F2: float], list[F3: float], list[F23: float] ]

    """
    # Carica le festività
    it_holidays = holidays.IT()  # type: ignore[attr-defined]

    # Azzera i dati precedenti
    for fascia in pz_data.keys():
        pz_data[fascia].clear()

    # Esamina ogni file XML negli ZIP (ordinandoli prima)
    priceFiles = priceArchive.namelist()
    fileNumber = len(priceFiles)

    for file_index, pf in enumerate(sorted(priceFiles)):
        _LOGGER.debug(f'Lettura del file "{pf}".')
        # Scompatta il file XML in memoria
        try:
            xml_prices_tree = et.parse(priceArchive.open(pf))
        except(Exception) as e:
            _LOGGER.debug(f'Errore: {e}')

        # Parsing dell'XML (1 file = 1 giorno)
        xml_prices_root = xml_prices_tree.getroot()
        price_element = xml_prices_root.find("Prezzi")

        if price_element == None:
            _LOGGER.warning(f'Il file non contiene dati validi.')
            fileNumber -= 1
            continue
        
        # Estrae la data dal primo elemento (sarà identica per gli altri)
        dat_string = price_element.find("Data")  # YYYYMMDD
        if dat_string == None or price_element.find("Ora") == None:
            _LOGGER.warning(f'Il file non contiene dati validi.')
            fileNumber -= 1
            continue

        # Controlla i prezzi zonali siano presenti, altrimenti passa al giorno successivo
        if price_element == None or price_element.find(zone) == None:
            fileNumber -= 1
            _LOGGER.warning(f'Nessun prezzo per zona "{zone}" trovato nel file.')
            continue

        # Converte la stringa giorno in data
        dat_date = date(
            int(dat_string.text[0:4]),
            int(dat_string.text[4:6]),
            int(dat_string.text[6:8]),
        )

        # Verifica la festività
        festivo = dat_date in it_holidays

        # Estrae le rimanenti informazioni
        for prezzi in xml_prices_root.iter("Prezzi"):
            # Estrae l'ora dall'XML
            ora = int(prezzi.find("Ora").text) - 1  # 1..24

            # Estrae la fascia oraria
            fascia = get_fascia_for_xml(dat_date, festivo, ora)

            # Estrae il prezzo zonale dall'XML in un float
            prezzo_string = prezzi.find(zone).text
            prezzo_string = prezzo_string.replace(".", "").replace(",", ".")
            prezzo_pz = float(prezzo_string) / 1000

            # Somma i valori dei diversi file per fascia per poter fare la media in seguito
            if file_index > 0:
                pz_data[Fascia.ORARIA][ora] += prezzo_pz
                pz_data[fascia][ora] += prezzo_pz
            else:
                pz_data[Fascia.ORARIA].append(prezzo_pz)
                pz_data[fascia].append(prezzo_pz)
    
    # Divide per il numero di file in cui erano presenti prezzi per completare la media
    for fascia, dati in pz_data.items():
        for ora in range(len(dati)):
            dati[ora] /= fileNumber

            if fascia == Fascia.ORARIA:
                _LOGGER.debug(f'Prezzo {zone} ora {ora}: {pz_data[Fascia.ORARIA][ora]}.')
    
    return pz_data