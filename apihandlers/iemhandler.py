import requests
import logging
import coloredlogs
import re
import json as j
from datetime import datetime, timedelta, timezone

settings = j.load(open('settings.json', 'r'))
l = logging.getLogger(__name__)
coloredlogs.install(level=settings['loglevel'], logger=l)

IEM_BASE = "https://mesonet.agron.iastate.edu"

"""
IEM (Iowa Environmental Mesonet) handler.

Unlike api.weather.gov, IEM doesn't hand back structured JSON for products --
it archives the raw NWS text bulletins as they were transmitted (AFOS/WMO
format) and lets you pull them by PIL (e.g. AFDVEF, HWOVEF, ZFPLOT, TORDMX).
This means less JSON-wrangling, and you can fetch literally any product type
NWS issues, not just the ones api.weather.gov happens to expose nicely.

The catch: IEM doesn't offer a documented single-call "give me the latest
product for this PIL" JSON endpoint, so we scrape their per-office daily
listing page (mesonet.agron.iastate.edu/wx/afos/list.phtml) to find the most
recent product ID, then fetch the raw text via api/1/nwstext/{product_id}.
"""


def _find_latest_pid(pil, office=None, lookback_days=2):
    """
    Finds the product_id (pid) of the most recently issued product for the
    given 6-character AFOS PIL (e.g. 'AFDDMX').
    """
    office = (office or pil[-3:]).upper()
    source = office if len(office) == 4 else f"K{office}"

    now = datetime.now(timezone.utc)
    for days_back in range(lookback_days):
        day = now - timedelta(days=days_back)
        params = {
            "source": source,
            "day": day.day,
            "month": day.month,
            "year": day.year,
        }
        try:
            resp = requests.get(f"{IEM_BASE}/wx/afos/list.phtml", params=params, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            l.error(f"IEM listing request failed for {pil}: {e}")
            continue

        # Relax the regex to just look for the pid in the URL, ignoring the HTML anchor text
        matches = re.findall(
            rf'p\.php\?pid=([0-9]{{12}}-[A-Z0-9]+-[A-Z0-9]+-{re.escape(pil)})',
            resp.text,
        )
        if matches:
            return matches[-1]  # entries are chronological; last == most recent

    l.warning(f"No products found on IEM for PIL {pil} in the last {lookback_days} day(s)")
    return None


def getProduct(pil, office=None):
    """
    Fetches the raw text of the most recently issued NWS product for the
    given AFOS PIL (e.g. 'AFDDMX', 'HWOVEF', 'ZFPLOT', 'TORDMX').
    Returns None if nothing could be found/retrieved.
    """
    pid = _find_latest_pid(pil, office=office)
    if pid is None:
        return None

    try:
        resp = requests.get(f"{IEM_BASE}/api/1/nwstext/{pid}", timeout=15)
        resp.raise_for_status()
        l.debug(f"IEM PRODUCT FETCHED\nPID {pid}")
        return resp.text
    except requests.RequestException as e:
        l.error(f"Failed to fetch IEM product text for {pid}: {e}")
        return None


def getSynopsis(office):
    """
    IEM equivalent of nwshandler.getSynopsis() -- pulls the latest Area
    Forecast Discussion for the given office and extracts the .SYNOPSIS
    section, same as the NWS handler does.
    """
    text = getProduct(f"AFD{office.upper()}")
    if text is None:
        return None

    start = '.SYNOPSIS...'
    end = "&&"

    if start not in text:
        l.debug(f"No .SYNOPSIS section found in latest AFD{office.upper()}")
        return None

    try:
        return text.split(start)[1].split(end)[0]
    except IndexError:
        return None


def getHWO(office):
    """Fetches the latest Hazardous Weather Outlook for the given office."""
    return getProduct(f"HWO{office.upper()}")


def getZoneForecast(pil):
    """
    Fetches a zone forecast package (ZFP) or similar bulletin in full, as
    issued. Unlike the NWS zones API, IEM doesn't split this out zone by
    zone -- you get the whole product, the same as it would go out over
    NOAA Weather Radio.
    """
    return getProduct(pil)
