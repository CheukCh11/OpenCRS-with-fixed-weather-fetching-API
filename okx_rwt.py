import os
import json
import SpeechHandler
import eas_tones

def generate_okx_rwt_same_header():
    # ZCZC-EAS-RWT-036061+0030-2361600-KOKX/NWS-
    # (036061 = New York / NYC county code, RWT = Required Weekly Test, +0030 = 30 min duration)
    return "ZCZC-EAS-RWT-036061+0030-2361600-KOKX/NWS-"

def generate_okx_rwt_text():
    return (
        "This is the National Weather Service office at Brookhaven National Labratory in Upton New York. "
        "The proceeding signal was a test of the NOAA All Hazards radio public alarm system on station KWO35 from New York City. "
        "During potentially dangerous weather situations, specially built receivers can be automatically "
        "activated by this signal to warn of impending hazard.\n\n"
        "Tests of the signal and receiver performance are normally conducted by the National Weather Service "
        "at 11 AM each Wednesday. If there is a threat of "
        "severe weather, the test will be postponed to the next available good weather day.\n\n"
        "Reception of this broadcast, and especially the warning alarm, will vary at any given location. "
        "This variability, normally more noticeable at greater distances from the transmitter, can occur even though "
        "you are using a good quality receiver in good working order.\n\n"
        "To provide the most consistent and dependable warning service possible, the warning alarm will be activated "
        "for hazards, watches and warnings for the following counties:\n\n"
        "In Southeast New York: Bronx, Kings, Nassau, New York, Orange, Putnam, Queens, Richmond, Rockland, Suffolk, and Westchester.\n\n"
        "In Northern and Central New Jersey: Bergen, Essex, Hudson, Hunterdon, Middlesex, Monmouth, Morris, Passaic, Somerset, Sussex, Union, and Warren.\n\n"
        "And in southwest Connecticut: Fairfield.\n\n"
        "Once again, this was only a test."
    )

def main():
    print("==================================================")
    print("      NWS OKX REQUIRED WEEKLY TEST (RWT)         ")
    print("==================================================")

    same_header_str = generate_okx_rwt_same_header()
    print(f"SAME Header: {same_header_str}")

    # 1. Generate & play SAME Header AFSK burst
    header_wav = eas_tones.generate_same_header(same_header_str, output_path="sounds/okx_rwt_same_header.wav")
    print("Playing NWR SAME Header Digital Tones...")
    eas_tones.play_audio(header_wav)

    # 2. Generate & play 1050 Hz Attention Tone (5 seconds for test)
    tone_wav = eas_tones.generate_1050hz_tone(duration_sec=5.0, output_path="sounds/1050hz_test.wav")
    print("Playing 1050 Hz Attention Tone...")
    eas_tones.play_audio(tone_wav)

    # 3. Save text & Speak via DECtalk
    rwt_text = generate_okx_rwt_text()

    with open("output.txt", "w", encoding="utf-8") as f:
        f.write(rwt_text)
        
    with open("temp_speech.txt", "w", encoding="utf-8") as f:
        f.write(rwt_text)

    voice = "[:nh :ph on :ra 215 :dv bf 20 hr 15 sr 20]"
    rate = 250

    if os.path.exists("settings.json"):
        with open("settings.json", "r") as f:
            cfg = json.load(f)
            dt_cfg = cfg.get("TTS", {}).get("dectalk", {})
            voice = dt_cfg.get("voice", voice)
            rate = dt_cfg.get("rate", rate)

    print("Speaking OKX RWT broadcast via DECtalk...")
    SpeechHandler.dectalk(r=rate, v=voice, filelocation="../temp_speech.txt")

    # 4. Generate & play SAME End of Message (EOM / NNNN) Tones
    eom_wav = eas_tones.generate_eom_tones(output_path="sounds/eom.wav")
    print("Playing SAME End of Message (EOM) Tones...")
    eas_tones.play_audio(eom_wav)

    print("OKX Required Weekly Test broadcast sequence complete!")

if __name__ == '__main__':
    main()
