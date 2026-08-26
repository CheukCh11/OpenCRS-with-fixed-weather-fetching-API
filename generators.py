import apihandlers.nwshandler as nwshandler
import apihandlers.iemhandler as iemhandler
import logging
import coloredlogs
import json as j
import time
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

settings = j.load(open('settings.json', 'r'))

logger = logging.getLogger(__name__)
coloredlogs.install(settings['loglevel'], logger=logger) 

def is_product_expired(text):
    """Parses NWS UGC strings (e.g., -241530-) to check if a product has expired."""
    # Look for the -DDHHMM- expiration string
    match = re.search(r'-(\d{2})(\d{2})(\d{2})-', text)
    if not match:
        return False  # If no expiration tag exists, assume it's valid

    exp_day = int(match.group(1))
    exp_hour = int(match.group(2))
    exp_minute = int(match.group(3))

    now = datetime.now(timezone.utc)
    try:
        exp_time = now.replace(day=exp_day, hour=exp_hour, minute=exp_minute, second=0, microsecond=0)

        # Handle month rollovers (e.g., today is the 31st, it expires on the 1st)
        if exp_day < 5 and now.day > 25:
            return False 
        elif exp_day > 25 and now.day < 5:
            return True 

        # If the current time is past the expiration time, drop the product
        if now > exp_time:
            return True
            
    except ValueError:
        pass
        
    return False

def clean_nws_product_text(text):
    # 1. Rescue the zone name before the header gets sliced
    zone_header = ""
    # Looks for the UGC code line, then captures the plain English name on the next line
    zone_match = re.search(r'[A-Z]{3}\d{3}[A-Z0-9\-]*\r?\n([A-Za-z0-9\s\(\),\./]+)-', text)
    if zone_match:
        clean_zone_name = zone_match.group(1).strip().replace('\n', ' ')
        zone_header = f"Forecast, for {clean_zone_name}.\n\n"

    # 2. Existing date slicing logic
    date_pattern = r'\d{3,4}\s+(?:AM|PM)\s+[A-Z]{3,4}\s+[A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+\d{4}'
    matches = list(re.finditer(date_pattern, text))
    if matches:
        last_match = matches[-1]
        text = text[last_match.end():]
        
    # 3. Existing cleanup logic
    text = re.sub(r'LAT\.\.\.LON[\s\S]*', '', text)
    text = re.sub(r'PRECAUTIONARY/PREPAREDNESS ACTIONS\.\.\.', '', text, flags=re.IGNORECASE)
    text = text.replace('*', '').replace('$$', '').replace('&&', '')
    
    # 4. Inject the rescued zone name at the very beginning
    text = zone_header + text
    return text.strip()

def parse_cli_to_speech(raw_cli):
    speech = "Here is the daily climate summary. "
    
    high_match = re.search(r'MAXIMUM\s+(\d+)', raw_cli)
    if high_match:
        speech += f"Yesterday's high temperature was {high_match.group(1)} degrees. "
        
    low_match = re.search(r'MINIMUM\s+(\d+)', raw_cli)
    if low_match:
        speech += f"The low temperature was {low_match.group(1)} degrees. "
        
    precip_match = re.search(r'PRECIPITATION.*?YESTERDAY\s+([T\d\.]+)', raw_cli, re.DOTALL)
    if not precip_match:
        precip_match = re.search(r'PRECIPITATION.*?TODAY\s+([T\d\.]+)', raw_cli, re.DOTALL)
        
    if precip_match:
        val = precip_match.group(1).strip()
        if val == 'T':
            speech += "Precipitation was a trace. "
        elif val:
            speech += f"Total precipitation was {val} inches. "
            
    return speech

def parse_pns_to_speech(raw_pns):
    cleaned = clean_nws_product_text(raw_pns)
    table_markers = [r'\.\.\.LOCATION\.\.\.', r'LOCATION\s+AMOUNT', r'LOCATION\s+MAX WIND', r'CITY LOCATION']
    
    for marker in table_markers:
        match = re.search(marker, cleaned, re.IGNORECASE)
        if match:
            narrative = cleaned[:match.start()].strip()
            disclaimer = "A complete tabular list of local spotter reports is available on the National Weather Service website."
            return f"{narrative}\n\n{disclaimer}"
            
    return cleaned

def parse_cwf_to_speech(raw_cwf):
    """Translates marine shorthand into spoken English before TTS processing."""
    # Get the clean base text with the rescued zone name
    text = clean_nws_product_text(raw_cwf)
    
    # RWR-style dictionary replacements
    replacements = {
        r'\bN\b': 'North', r'\bS\b': 'South', r'\bE\b': 'East', r'\bW\b': 'West',
        r'\bNW\b': 'Northwest', r'\bNE\b': 'Northeast', r'\bSW\b': 'Southwest', r'\bSE\b': 'Southeast',
        r'\bkt\b': 'knots', r'\bft\b': 'feet',
        r'\btstm\b': 'thunderstorm', r'\btstms\b': 'thunderstorms',
        r'\bMON\b': 'Monday', r'\bTUE\b': 'Tuesday', r'\bWED\b': 'Wednesday', 
        r'\bTHU\b': 'Thursday', r'\bFRI\b': 'Friday', r'\bSAT\b': 'Saturday', r'\bSUN\b': 'Sunday'
    }
    
    # Apply the dictionary directly to the text
    for pattern, word in replacements.items():
        text = re.sub(pattern, word, text, flags=re.IGNORECASE)
        
    return text

def parse_srf_to_speech(raw_srf):
    """Parses tabular Surf Zone Forecasts into spoken English."""
    # 1. Clean the NWS header and zone
    text = clean_nws_product_text(raw_srf)
    
    # 2. Chop off the Rip Current risk definitions at the bottom of the file
    # (Prevents the radio from reading a 3-minute glossary every broadcast)
    if "&&" in text:
        text = text.split("&&")[0].strip()
        
    # 3. Replace the tabular dots (........) with a comma for a natural TTS pause
    text = re.sub(r'\.{2,}', ', ', text)
    
    # 4. Expand abbreviations commonly used in the wind and weather sections
    replacements = {
        r'\bN\b': 'North', r'\bS\b': 'South', r'\bE\b': 'East', r'\bW\b': 'West',
        r'\bNW\b': 'Northwest', r'\bNE\b': 'Northeast', r'\bSW\b': 'Southwest', r'\bSE\b': 'Southeast',
        r'\bmph\b': 'miles per hour',
    }
    
    for pattern, word in replacements.items():
        text = re.sub(pattern, word, text, flags=re.IGNORECASE)
        
    return text.strip()

import re


def parse_rwr_to_speech(raw_text):
    """
    Replicates the official NOAA BMH conversational narrative style.
    Handles the highly detailed primary station, brief secondary stations, and coastal marine formatting.
    """
    lines = raw_text.split('\n')
    
    # Extract report time (e.g., "800 AM" -> "8:00 AM")
    time_match = re.search(r'(\d{1,2})(\d{2})\s+(AM|PM)', raw_text)
    if time_match:
        time_str = f"{time_match.group(1)}:{time_match.group(2)} {time_match.group(3).lower()}."
    else:
        time_str = "the top of the hour."

    speech = "Here are the current conditions. "
    
    sky_dict = {
        "SUNNY": "sunny", "MOSUNNY": "mostly sunny", "PTSUNNY": "partly sunny", "PTSNY": "partly sunny",
        "CLOUDY": "cloudy", "MOCLDY": "mostly cloudy", "POCLDY": "partly cloudy", "PTCLDY": "partly cloudy",
        "CLEAR": "clear", "FAIR": "fair", "FOG": "foggy", "LGT RAIN": "light rain", "RAIN": "rain"
    }
    
    dir_dict = {
        "N": "North", "S": "South", "E": "East", "W": "West",
        "NE": "Northeast", "NW": "Northwest", "SE": "Southeast", "SW": "Southwest", "VRB": "variable"
    }

    # Expand cryptic abbreviations to match official radio pronunciation
    station_expansions = {
        "Bronx Lehman C": "the Bronx Botanical Gardens",
        "LaGuardia Arpt": "LaGuardia Airport",
        "Kennedy Intl": "Kennedy",
        "Brooklyn Coll": "Brooklyn College",
        "Newark/Liberty": "Newark",
        "Teterboro Arpt": "Teterboro",
        "MacArthur/ISP": "Islip",
        "Wtrbury/Oxford": "Waterbury Oxford",
        "Bradley Intl": "Bradley International Airport",
        "NY Harb Entrance": "New York Harbor entrance buoy",
        "20 S Fire Island": "20 nautical miles south of Fire Island Inlet",
        "15 E Barnegat Li": "15 nautical miles east of Barnegat Light",
        "23 SSW Montauk P": "the buoy 23 nautical miles south-southwest of Montauk Point",
        "Western LI Sound": "the western sound",
        "Central LI Sound": "Central Sound"
    }

    # Keywords to completely ignore so they don't get read as regions
    skip_keywords = [
        "KEY", "CITY", "SKY/WX", "STATION/POSITION", "Note:", "$$", 
        "ASUS41", "RWROKX", "OSOOKX", "MINUTES", "OBSERVATIONS", 
        "Regional Weather", "State Weather", "National Weather"
    ]

    is_first_station = True
    in_marine = False

    for line in lines:
        line_str = line.rstrip()
        
        # 1. Skip empty lines and formatting artifacts
        if not line_str or line_str.startswith("$$") or line_str.startswith(">"):
            continue
        if re.search(r'^[A-Z]{3}\d{3}', line_str):  # Skip UGC codes
            continue
        if re.search(r'\d{3,4}\s+(AM|PM)\s+(EDT|EST|CDT|CST)', line_str): # Skip date header
            continue

        clean_line = line_str.strip()

        # 2. Skip NWS meta-text and trigger Marine transition
        if any(kw in clean_line for kw in skip_keywords):
            if "Coastal Marine Observations" in clean_line:
                in_marine = True
                speech += " Here are the latest reports on the coastal waters. "
            continue

        # 3. Catch missing stations EARLY before region transition logic
        if "NOT AVBL" in line_str or "MISG" in line_str[:25]:
            # Cleanly split the string instead of guessing the character index
            station_raw = line_str.split("NOT AVBL")[0].split("MISG")[0].strip()
            speech += f"The report from {station_expansions.get(station_raw, station_raw)} was not available. "
            continue

        # 4. Handle Regional Transitions
        if len(clean_line) < 32 and not any(c.isdigit() for c in clean_line):
            if "New York City Metro" in clean_line:
                speech += " Elsewhere in the metropolitan area, "
            elif "Long Island" in clean_line:
                speech += " Across Long Island, "
            elif "Hudson Valley" in clean_line:
                speech += " In the Hudson Valley, "
            elif "New Jersey" in clean_line:
                speech += " In New Jersey, "
            elif "Eastern Pennsylvania" in clean_line:
                speech += " In Eastern Pennsylvania, "
            elif "Connecticut" in clean_line:
                speech += " In Connecticut, "
            elif clean_line not in ["In CT", "In RI", "In MA"]:
                speech += f" In {clean_line}, "
            continue

        # === 5. MARINE PARSER ===
        if in_marine:
            if len(line_str) > 20:
                station = line_str[:16].strip()
                air_tmp = line_str[33:36].strip() if len(line_str) >= 36 else ""
                sea_tmp = line_str[36:39].strip() if len(line_str) >= 39 else ""
                wind_raw = line_str[40:53].strip() if len(line_str) >= 53 else ""
                wave_raw = line_str[64:].strip() if len(line_str) > 64 else ""
                
                station_name = station_expansions.get(station, station)
                marine_sentence = f"At {station_name}, "
                
                if wind_raw and wind_raw != "N/A" and "MISG" not in wind_raw:
                    w_parts = [x.strip() for x in wind_raw.split('/') if x.strip()]
                    if len(w_parts) >= 2 and w_parts[0].isdigit():
                        deg, spd = int(w_parts[0]), w_parts[1]
                        gust = w_parts[2] if len(w_parts) > 2 else ""
                        
                        compass = ["North", "Northeast", "East", "Southeast", "South", "Southwest", "West", "Northwest", "North"]
                        dir_name = compass[round(deg / 45) % 8]
                        
                        marine_sentence += f"winds were {dir_name} at {spd} knots"
                        if gust and gust != "N/A" and gust.isdigit():
                            marine_sentence += f", gusting to {gust} knots"
                        marine_sentence += ". "
                        
                if air_tmp and air_tmp != "N/A" and air_tmp.isdigit():
                    marine_sentence += f"The air temperature was {air_tmp} degrees. "
                if sea_tmp and sea_tmp != "N/A" and sea_tmp.isdigit():
                    marine_sentence += f"sea temperature {sea_tmp} degrees. "
                    
                if wave_raw and wave_raw != "N/A":
                    wv_parts = [x.strip() for x in wave_raw.split('/') if x.strip()]
                    if len(wv_parts) >= 2 and wv_parts[0].isdigit():
                        marine_sentence += f"Wave heights {wv_parts[0]} feet, wave period {wv_parts[1]} seconds. "
                
                if marine_sentence != f"At {station_name}, ":
                    speech += marine_sentence
                    
        # === 6. LAND PARSER ===
        else:
            if len(line_str) >= 28:
                city_raw = line_str[:15].strip()
                sky_raw = line_str[15:24].strip()
                tmp = line_str[24:28].strip()
                dp = line_str[28:31].strip()
                rh = line_str[31:35].strip()
                wind_raw = line_str[35:46].strip()
                pres_raw = line_str[46:54].strip()

                if not tmp.isdigit():
                    continue

                city = station_expansions.get(city_raw, city_raw)
                sky = sky_dict.get(sky_raw, sky_raw.lower().replace("mo", "mostly ").replace("pt", "partly "))
                if sky == "n/a": sky = ""

                wind_sentence = ""
                if wind_raw == "CALM":
                    wind_sentence = "The wind was calm"
                elif wind_raw and wind_raw not in ["N/A", "MISG"]:
                    match = re.match(r'([A-Z]+)(\d+)(?:G(\d+))?', wind_raw)
                    if match:
                        d, s, g = match.groups()
                        d_full = dir_dict.get(d, d)
                        wind_sentence = f"The wind was {d_full} at {s} miles an hour"
                        if g: wind_sentence += f", gusting to {g}"

                if is_first_station:
                    speech += f"As of {time_str} at {city}, "
                    if sky: speech += f"it was {sky}; "
                    speech += f"the temperature was {tmp} degrees"
                    if dp.isdigit(): speech += f", the dew point {dp}"
                    if rh.isdigit(): speech += f", and the relative humidity {rh} percent. "
                    else: speech += ". "
                    
                    if wind_sentence: speech += f"{wind_sentence}. "
                    
                    if pres_raw and pres_raw != "N/A":
                        val = pres_raw[:-1]
                        trend = pres_raw[-1]
                        t_str = "and steady"
                        if trend == 'R': t_str = "and rising"
                        elif trend == 'F': t_str = "and falling"
                        speech += f"The pressure was {val} inches {t_str}. "
                        
                    is_first_station = False
                    
                else:
                    speech += f"At {city}, "
                    if sky:
                        speech += f"it was {sky}, with a temperature of {tmp}. "
                    else:
                        speech += f"the temperature was {tmp}. "
                        
    return speech.replace("  ", " ").strip()

def extract_zone_name(text):
    """Extracts the plain English location name following UGC zone codes."""
    zone_match = re.search(r'[A-Z]{3}\d{3}[A-Z0-9\-]*\r?\n([A-Za-z0-9\s\(\),\./]+)-', text)
    if zone_match:
        return zone_match.group(1).strip().replace('\n', ' ')
    return None

def clean_nws_product_text(text):
    """Cleans up raw NWS product text timestamps, footers, and meta tags."""
    date_pattern = r'\d{3,4}\s+(?:AM|PM)\s+[A-Z]{3,4}\s+[A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+\d{4}'
    matches = list(re.finditer(date_pattern, text))
    if matches:
        last_match = matches[-1]
        text = text[last_match.end():]
        
    text = re.sub(r'LAT\.\.\.LON[\s\S]*', '', text)
    text = re.sub(r'PRECAUTIONARY/PREPAREDNESS ACTIONS\.\.\.', '', text, flags=re.IGNORECASE)
    text = text.replace('*', '').replace('$$', '').replace('&&', '')
    
    return text.strip()

def process_product_list(pil_list, office, my_zones, product_intros):
    chunk_txt = ""
    chunk_playlist = []
    
    for pil in pil_list:
        prefix = pil[:3]
        
        # 1. Daily Climate
        if prefix == "CLI":
            product = iemhandler.getProduct(pil, office=office)
            if product:
                cli_text = parse_cli_to_speech(product)
                chunk_txt += cli_text + "\n---------------------------\n"
                chunk_playlist.append(cli_text)
            else:
                logger.warning(f"Could not retrieve {pil} from IEM")
            continue
            
        # 2. Public Information Statements
        if prefix == "PNS":
            product = iemhandler.getProduct(pil, office=office)
            if product:
                if any(zone in product for zone in my_zones):
                    pns_text = parse_pns_to_speech(product)
                    intro = product_intros.get(prefix, "Here is a Public Information Statement.")
                    pns_chunk = f"{intro}\n\n{pns_text}"
                    chunk_txt += pns_chunk + "\n---------------------------\n"
                    chunk_playlist.append(pns_chunk)
            continue

        # 3. Coastal Waters Forecast
        if prefix == "CWF":
            product = iemhandler.getProduct(pil, office=office)
            if product and any(zone in product for zone in my_zones):
                zone_name = extract_zone_name(product)
                cwf_text = parse_cwf_to_speech(product)
                intro = f"Here is the Coastal Waters Forecast for {zone_name}." if zone_name else "Here is the Coastal Waters Forecast."
                cwf_chunk = f"{intro}\n\n{cwf_text}"
                chunk_txt += cwf_chunk + "\n---------------------------\n"
                chunk_playlist.append(cwf_chunk)
            continue
        # Surf Zone Forecast
        if prefix == "SRF":
            product = iemhandler.getProduct(pil, office=office)
            if product and any(zone in product for zone in my_zones):
                zone_name = extract_zone_name(product)
                srf_text = parse_srf_to_speech(product)
                intro = f"Here is the Surf Zone Forecast for {zone_name}." if zone_name else "Here is the Surf Zone Forecast."
                srf_chunk = f"{intro}\n\n{srf_text}"
                chunk_txt += srf_chunk + "\n---------------------------\n"
                chunk_playlist.append(srf_chunk)
            continue
        # 4. Regional Weather Roundups / State Summaries
        if prefix in ["RWR", "OSO"]:
            product = iemhandler.getProduct(pil, office=office)
            if product:
                obs_text = parse_rwr_to_speech(product)
                intro = product_intros.get(prefix, f"Here is the latest {prefix}.")
                obs_chunk = f"{intro}\n\n{obs_text}"
                chunk_txt += obs_chunk + "\n---------------------------\n"
                chunk_playlist.append(obs_chunk)
            else:
                logger.warning(f"Could not retrieve {pil} from IEM")
            continue

        # 5. Routine / Warning Products
        logger.info(f"Getting product {pil} from IEM")
        product = iemhandler.getProduct(pil, office=office)
        
        if product:
            if is_product_expired(product):
                logger.info(f"Skipped {pil} - product has expired.")
                continue
                
            if any(zone in product for zone in my_zones):
                cleaned_product = clean_nws_product_text(product)
                zone_name = extract_zone_name(product)
                
                # Format intros specifically for HWO, ZFP, or general products
                if prefix == "HWO":
                    intro = f"And now, here is the Hazardous Weather Outlook for {zone_name}." if zone_name else "And now here is the Hazardous Weather Outlook."
                elif prefix == "ZFP":
                    intro = f"Here is the local forecast for {zone_name}." if zone_name else "Here is the local forecast."
                else:
                    base_intro = product_intros.get(prefix, f"Here is the latest {prefix} product.")
                    intro = f"{base_intro.rstrip('.')} for {zone_name}." if zone_name else base_intro

                product_chunk = f"{intro}\n\n{cleaned_product}"
                chunk_txt += product_chunk + "\n---------------------------\n"
                chunk_playlist.append(product_chunk)
            else:
                logger.info(f"Skipped {pil} - none of your configured zones were found in the text.")
        else:
            logger.warning(f"Could not retrieve {pil} from IEM")
            
    return chunk_txt, chunk_playlist

def genIEM():
    outfile = open('output.txt', "w+")
    full_txt = ""
    playlist = []

    office = settings['IEMsettings']['ForecastOffice']
    my_zones = settings['NWSsettings']['Zones']

    urgent_prefixes = ["TOR", "SVR", "FFW", "SMW", "FLW", "SPS", "SVS", "TOA", "SVA", "FFS", "MWS", "FLS", "CDW"]
    all_pils = settings['IEMsettings']['Products']
    
    urgent_pils = [pil for pil in all_pils if pil[:3] in urgent_prefixes]
    routine_pils = [pil for pil in all_pils if pil[:3] not in urgent_prefixes]

    product_intros = {
        "ZFP": "Here is the local",
        "CLI": "Here is the daily climate report.",
        "PNS": "Here is a Public Information Statement from the National Weather Service.",
        "RWR": "Here is the regional weather roundup.",
        "OSO": "Here is the state weather summary.",
        "TOR": "The following is an urgent weather message from the National Weather Service.",
        "TOA": "This is a tornado watch.",
        "FFW": "The following is an urgent weather message from the National Weather Service.",
        "SMW": "The following is an urgent weather message from the National Weather Service.",
        "FFS": "The following is a Flash Flood Statement from the National Weather Service.",
        "FLW": "The following is an urgent weather message from the National Weather Service.",
        "CWF": "Here is the Coastal Waters Forecast.",
        "SVR": "The following is an urgent weather message from the National Weather Service.",
        "SVA": "This is a Severe Thunderstorm Watch.",
        "SPS": "This is a Special Weather Statement.",
        "HWO": "And now,",
        "MWS": "This is a Marine Weather Statement.",
    }

    # 1. Define the intro strings first
    intro_part_1 = (
        "You are listening to NOAA's All-Hazards Radio, station K W O 35 in New York City. "
        "This broadcast originates from the National Weather Service forecast office located on the grounds of "
        "Brookhaven National Laboratory in Upton New York. Station K W O 35 broadcasts at a frequency of 162.55 Megahertz, "
        "this service is not official and uses the Iowa Environmental Mesonet API to fetch newest alerts."
    )
    eastern_time_obj = datetime.now(ZoneInfo("America/New_York"))
    hour = eastern_time_obj.hour % 12 or 12
    eastern_time_str = f"{hour}:{eastern_time_obj.strftime('%M %p %Z')}"
    intro_part_2 = f"The current time is {eastern_time_str}."

    # 2. Append the text to the playlist and text file
    full_txt += f"{intro_part_1}\n\n{intro_part_2}\n\n"
    playlist.append(intro_part_1) 
    playlist.append(intro_part_2) 

    # --- 3. CUSTOM AUDIO INJECTION ---
    custom_audio = settings.get("CustomAudio", {})
    
    if custom_audio.get("enabled", False):
        if custom_audio.get("play_intro_text", False):
            intro_msg = custom_audio.get("intro_text", "And now, a special announcement.")
            playlist.append(intro_msg)
            full_txt += f"{intro_msg}\n\n"
            
        playlist.append({
            "type": "audio", 
            "path": custom_audio.get("path", "")
        })
        
    # ------------------------------

    # 4. Process URGENT Products
    if urgent_pils:
        urgent_txt, urgent_playlist = process_product_list(urgent_pils, office, my_zones, product_intros)
        full_txt += urgent_txt
        playlist.extend(urgent_playlist)

    # 5. Process the Synopsis
    synopsis = iemhandler.getSynopsis(office)
    if synopsis:
        syn_text = "Here is the regional Synopsis from the National Weather Service:\n\n" + synopsis.strip()
        full_txt += syn_text + "\n---------------------------\n"
        playlist.append(syn_text)

    # 6. Process ROUTINE Products
    if routine_pils:
        routine_txt, routine_playlist = process_product_list(routine_pils, office, my_zones, product_intros)
        full_txt += routine_txt
        playlist.extend(routine_playlist)
            
    if full_txt:
        outfile.write(full_txt)
        outfile.close()
        logger.info("Wrote to output.txt successfully!")
        return playlist
    else:
        logger.error("The generator failed to provide a text output.")
        return []

def genNWS():
    return []
def genIBM():
    return []

