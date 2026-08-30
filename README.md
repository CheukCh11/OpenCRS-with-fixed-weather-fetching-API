# OpenCRS-with-fixed-weather-fetching-API
An updated and fixed fork of [Zeexel/OpenCRS](https://github.com/Zeexel/forecast-gen) and [wagwan-piffting-blud/OpenCRS](https://github.com/wagwan-piffting-blud/OpenCRS).

---

Hiya! This is basically a somewhat fixed version of @wagwan-piffting-blud's OpenCRS repository that I managed to fix with help from Gemini (well, I could've used Claude, but oh well, it works anyway)
To be more specific, it's some of the API in there that have been fixed, the "weather-product fetching" API, actually. But good news for you people who want to try this out on Mac, because it actually does run with Wine!
although... I don't actually know how most (if not all) of the mumbo jumbo works, so here's an explanation from Gemini:

The goal of **OpenCRS** is to replicate the National Weather Service's **Console Replacement System (CRS)** for automated weather radio broadcasts. It continuously pulls real-time weather bulletins from NWS APIs, translates raw shorthand and tabular data into natural spoken English, and broadcasts it through Text-to-Speech (TTS) engines like **DECtalk** or **Balcon**.

---

## What's New & Fixed in This Fork

* **Zone Name Injection:** Rescues and speaks plain-English zone names (e.g., *"Here is the local forecast for New York (Manhattan)"*) across weather products.
* **Marine & Coastal Forecast Parsers:** Automatically translates marine shorthand (`kt` → `knots`, `ft` → `feet`, `tstms` → `thunderstorms`, direction codes) in Coastal Waters Forecasts (CWF) and Surf Zone Forecasts (SRF).
* **Tabular Surf Zone Parser:** Converts dot-matrix tables (`Rip Current Risk............Moderate`) into readable, natural sentences.
* **DECtalk Execution Fix (`[WinError 2]`):** Fixed path resolution bugs when calling `say.exe` on Windows and Linux/macOS via Wine.


* **Expiration Guard:** Reads Universal Geographic Code (UGC) headers (`-DDHHMM-`) to automatically drop expired watches and warnings.
* **Custom Audio Splices:** Seamlessly injects `.wav` audio files (like alert tones or line splices) into the broadcast loop.

---

## How OpenCRS Works

```
[ NWS / IEM APIs ] ──► [ Expiration & Zone Filters ] ──► [ Conversational Parsers ] ──► [ DECtalk / Balcon TTS ]

```

1. **Fetching (`apihandlers/`):** Pulls raw text products from the Iowa Environmental Mesonet (IEM) or NWS APIs.


2. **Filtering & Slicing (`generators.py`):** Filters out expired products using UGC timestamps and isolates active zones specified in `settings.json`.


3. **Conversational Parsing:** Strips unwanted metadata headers and converts raw shorthand, climate statistics, and observation tables (RWR) into natural sentences.
4. **Broadcast Pipeline (`main.py`):** Sequences station identification, current Eastern time announcements, custom audio splices, urgent alerts, and routine forecasts into a single stream.
5. **TTS Output (`SpeechHandler.py`):** Cleans text to prevent DECtalk bracket crashes and feeds output directly to the TTS engine.

---

## Prerequisites

* **Python 3.8+**
* **Wine** (Only required if running DECtalk on Linux or macOS)



---

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/OpenCRS.git
cd OpenCRS

```

### 2. Install Dependencies

```bash
pip install -r requirements.txt

```

*(Or manually install: `pip install requests coloredlogs`)*

---

## TTS Engine Setup

### Option 1: DECtalk (Default & Included)

DECtalk is the classic voice engine for NOAA Weather Radio simulations.

1. Create a `dectalk/` folder in the root directory if it does not exist.
2. Ensure `say.exe` and its supporting DLL files (`dectalk.dll`, `dtalk_us.dic`, etc.) are placed inside the `dectalk/` folder:
```text
OpenCRS/
├── dectalk/
│   ├── say.exe
│   ├── dectalk.dll
│   └── dtalk_us.dic
├── main.py
├── generators.py
└── settings.json

```


3. **Test DECtalk manually via Terminal:**
* **Windows:**
```cmd
cd dectalk
echo Hello world. | say.exe

```


* **Linux / macOS:**
```bash
cd dectalk
echo "Hello world." | wine say.exe

```





### Option 2: Balcon (Balabolka CLI)

[Balcon](http://www.cross-plus-a.com/bconsole.htm) is a free command-line reader.

1. Download Balcon and place the `balcon/` folder in the root OpenCRS directory.


2. List available voices on your system:
```cmd
balcon.exe -l

```


3. Update the voice name under `"balcon"` in `settings.json`.



---

## Configuration (`settings.json`)

Configure your broadcast station, forecast office, monitored zones, and TTS preferences:

```json
{
  "loglevel": "DEBUG",
  "OpenCRSsettings": {
    "system": "imperial",
    "apihandler": "iem"
  },
  "IEMsettings": {
    "ForecastOffice": "OKX",
    "Products": [
      "HWOOKX",
      "ZFPOKX",
      "CLINYC",
      "PNSOKX",
      "CWFOKX",
      "SRFOKX",
      "RWROKX",
      "OSOOKX"
    ]
  },
  "NWSsettings": {
    "Zones": [
      "NYZ072",
      "NYC061",
      "ANZ350"
    ]
  },
  "CustomAudio": {
    "enabled": true,
    "play_intro_text": false,
    "path": "sounds/splice-xj-phoneline-v2.wav"
  },
  "TTS": {
    "enabled": true,
    "engine": "dectalk",
    "dectalk": {
      "rate": 250,
      "voice": "[:Nh :PH ON :RA 207 :DV BF 40 HR 22 SR 44]"
    }
  }
}

```

---

## Running OpenCRS

Start the broadcast polling loop:

```bash
python main.py

```

The script will query weather APIs, parse statements, output the full broadcast script to `output.txt`, and trigger the TTS voice.

---

## Troubleshooting

* **`[WinError 2] The system cannot find the file specified`:** Ensure `say.exe` and its `.dll` files are directly inside the `dectalk/` folder.
* **DECtalk executes but produces no audio:** DECtalk buffers speech until it encounters ending punctuation (`.`, `!`, `?`). Ensure text strings end with punctuation, and check Windows Volume Mixer to verify `say.exe` is not muted.
* **Abbreviations not translating:** Ensure your `IEMsettings.Products` in `settings.json` match the product PILs (e.g., `CWFOKX` or `SRFOKX`).
* If it is not working, try doing `pip install tzdata`, it should work

---

### some things to note:
- there is Emergency Alert System (EAS) tone logic in here, so please DO not broadcast them on the air; otherwise, some people from the FCC might not be happy with that >:(
- Linux version is **NOT GUARANTEED** to work; I have not had people test on this. If it doesn't work, please just let me know.
- Windows is **NOT GUARANTEED** to work at times. If there are any issues, please create a post in the Issues section.
