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


def extract_xml(priceArchive: ZipFile, usageArchive: ZipFile, pz_data: dict, zone: str) -> tuple[list[dict[Fascia, list[float]]], list[dict[Fascia, list[float]]]]:
    """Estrae i valori dei prezzi per ogni fascia da un archivio zip contenente un XML per giorno del mese.

    Returns tuple(zonali, consumi zonali):
    List[ list[ORARIA: float], list[F1: float], list[F2: float], list[F3: float], list[F23: float] ]

    """
    # Carica le festività
    it_holidays = holidays.IT()  # type: ignore[attr-defined]
    zone = {"prezzi": zone, "consumo": zone}

    zone_usage: PricesData = PricesData().data
    # Azzera i dati precedenti
    for fascia in pz_data.keys():
        pz_data[fascia] = [0] * 24

    # Esamina ogni file XML negli ZIP (ordinandoli prima)
    priceFiles = priceArchive.namelist()
    usageFiles = usageArchive.namelist()
    fileNumber = {"prezzi": len(priceFiles), "consumo": len(usageFiles)}

    for pf, uf in zip(sorted(priceFiles), sorted(usageFiles)):
        _LOGGER.debug(f'Lettura dei file "{pf}" e "{uf}".')
        # Scompatta il file XML in memoria
        try:
            xml_prices_tree = et.parse(priceArchive.open(pf))
            xml_usage_tree = et.parse(usageArchive.open(uf))
        except(Exception) as e:
            _LOGGER.debug(f'Errore: {e}')

        # Parsing dell'XML (1 file = 1 giorno)
        xml_prices_root = xml_prices_tree.getroot()
        xml_usage_root = xml_usage_tree.getroot()
        price_element = xml_prices_root.find("Prezzi")
        usage_element = xml_usage_root.find("marketintervaldetail")

        if price_element == None or usage_element == None:
            _LOGGER.debug(f'I file non contengono dati validi.')
            continue
        
        # Estrae la data dal primo elemento (sarà identica per gli altri)
        dat_string = price_element.find("Data")  # YYYYMMDD
        if dat_string == None or price_element.find("Ora") == None:
            _LOGGER.debug(f'I file non contengono dati validi.')
            continue

        # Controlla che tutti i file siano validi, altrimenti passa al giorno successivo
        valido, zone, fileNumber, pzo = convalida_xml(price_element, usage_element, zone, fileNumber)
        if not valido:
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
        for prezzi, consumo in zip(xml_prices_root.iter("Prezzi"), xml_usage_root.iter("marketintervaldetail")):
            # Estrae l'ora dall'XML
            ora = int(prezzi.find("Ora").text) - 1  # 1..24

            # Estrae la fascia oraria
            fascia = get_fascia_for_xml(dat_date, festivo, ora)

            # Estrae il prezzo zonale dall'XML in un float
            if pzo:
                prezzo_string = prezzi.find(zone["prezzi"]).text
                prezzo_string = prezzo_string.replace(".", "").replace(",", ".")
                prezzo_pz = float(prezzo_string) / 1000

                # Somma i valori dei diversi file per fascia per poter fare la media in seguito
                pz_data[Fascia.ORARIA][ora] += prezzo_pz
                pz_data[fascia][ora] += prezzo_pz
                if fascia == Fascia.F2 or fascia == Fascia.F3:
                    pz_data[Fascia.F23][ora] += prezzo_pz
                
                # Estrae i consumi previsti per la zona selezionata per fasce, per poter fare la media ponderata dei prezzi zonali
                if pzo != "solo prezzi":
                    consumo_string = consumo.find(zone["consumo"]).text
                    consumo_string = consumo_string.replace(".", "").replace(",", ".")
                    zone_usage[fascia][ora] += float(consumo_string) / 1000
                    zone_usage[Fascia.ORARIA][ora] += zone_usage[fascia][ora]

                    if fascia == Fascia.F2 or fascia == Fascia.F3:
                        zone_usage[Fascia.F23][ora] += zone_usage[fascia][ora]
    
    # Divide per il numero di file in cui erano presenti prezzi per completare la media
    for fascia in pz_data.keys():
        for ora in range(24):
            pz_data[fascia][ora] /= fileNumber["prezzi"]
            zone_usage[fascia][ora] /= fileNumber["consumo"]

            if fascia == Fascia.ORARIA:
                _LOGGER.debug(f'Dati {zone["prezzi"]} ora {ora}: prezzo ({pz_data[Fascia.ORARIA][ora]}), consumi ({zone_usage[Fascia.ORARIA][ora]}).')
    
    return pz_data, zone_usage


def convalida_xml(price_element, usage_element, zone: dict[str, str], fileNumber: dict[str, float]):
    '''Controlla se gli elementi contegono i dati necessari.'''
    
    # Controlla i prezzi zonali siano presenti, altrimenti passa al giorno successivo
    if price_element == None or price_element.find(zone["prezzi"]) == None:
        fileNumber["prezzi"] -= 1
        _LOGGER.warning(f'Nessun prezzo zonale per "{zone['prezzi']}" trovato nei file.')
        return False, zone, fileNumber, None
    
    # Controlla che ci siano i dati sui consumi della zona selezionata, altrimenti passa al giorno successivo
    # Zona "NAT" e tutte quello non presenti in PHYSICAL_ZONES diventano "Totale"
    if usage_element == None or usage_element.find(zone["consumo"] if zone["consumo"] in PHYSICAL_ZONES else "Totale") == None:
        _LOGGER.warning(f'I file non contengono dati sui consumi per "{zone['consumo']}", il calcolo dei prezzi zonali per le fasce sarà più impreciso.')
        fileNumber["consumo"] -= 1
        return True, zone, fileNumber, "solo prezzi"
    
    if zone["consumo"] == "NAT": zone["consumo"] = "Totale"
    
    return True, zone, fileNumber, True