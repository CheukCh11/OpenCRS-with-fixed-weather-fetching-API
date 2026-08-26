import asyncio
import SpeechHandler
import generators
import requests as r
import coloredlogs, logging
import json as j
import subprocess
import platform

settings = j.load(open('settings.json', 'r'))
logger = logging.getLogger(__name__)
coloredlogs.install(settings['loglevel'], logger=logger)    # I'd recommend keeping this at DEBUG

async def main():
    logger.info('Starting OpenCRS..')

    if settings['OpenCRSsettings']['apihandler'] == "noaa":
        logger.debug("Generating output.txt using NOAA's API..")
        generator = generators.genNWS
    elif settings['OpenCRSsettings']['apihandler'] == "iem":
        logger.debug("Generating output.txt using the IEM text product archive..")
        generator = generators.genIEM
    elif settings['OpenCRSsettings']['apihandler'] == "ibm":
        logger.debug("Generating output.txt using IBM's API..")
        generator = generators.genIBM
    else:
        logger.critical("Unknown API handler configured!")
        return

    TTSoptions = settings["TTS"]

    if TTSoptions["enabled"]:
        logger.warning("TTS implementation is very janky! It relies on DECTalk or Balabolka.")
        TTSengine = TTSoptions['engine']
        DTSettings = TTSoptions['dectalk']
        BALSettings = TTSoptions['balcon']
    else:
        TTSengine = None

    # Main polling loop
    while True:
        print("Checking for new products...")
        playlist = generator()

        if TTSoptions["enabled"] and playlist:
            for item in playlist:
                
                # Check if the playlist item is Text or Audio
                is_audio = False
                if isinstance(item, dict) and item.get("type") == "audio":
                    is_audio = True
                    audio_path = item.get("path")
                else:
                    text_chunk = item if isinstance(item, str) else item.get("content", "")

                # 1. Handle standard TTS Text
                if not is_audio:
                    with open("temp_speech.txt", "w", encoding="utf-8") as f:
                        f.write(text_chunk)

                    if TTSengine == "dectalk":
                        SpeechHandler.dectalk(
                            r=DTSettings['rate'],
                            v=DTSettings['voice'],
                            filelocation="../temp_speech.txt"
                        )
                    elif TTSengine == "balcon":
                        SpeechHandler.balcon(
                            voice=BALSettings['voice'],
                            volume=BALSettings['volume'],
                            rate=BALSettings['speed'],
                            filelocation="../temp_speech.txt"
                        )
                        
                # 2. Handle Real-Voice Custom Audio Files
                else:
                    print(f"Playing custom audio: {audio_path}")
                    try:
                        # Uses macOS's native 'afplay' or Windows 'start' to play the audio file seamlessly
                        if platform.system() == "Darwin":
                            subprocess.run(["afplay", audio_path])
                        elif platform.system() == "Windows":
                            import winsound
                            winsound.PlaySound(audio_path, winsound.SND_FILENAME)
                        else:
                            subprocess.run(["aplay", audio_path])
                    except Exception as e:
                        logger.error(f"Failed to play custom audio file: {e}")
                    
        print("Cycle complete. Sleeping for 2 seconds before refreshing...")
        await asyncio.sleep(2)

if __name__ == '__main__':
    ver = '0.2-GIT'     # OpenCRS version
    noaa = r.get('https://api.weather.gov')

    #Github release check
    try:
        github = r.get('https://api.github.com/repos/Zeexel/OpenCRS/releases/latest').json()
        if github['name'] != ver:
            logger.warning(f"Version {github['name']} is currently out! You're using version {ver}.")
        else:
            logger.info("Using the latest build of OpenCRS!")
    except Exception as e:
        logger.error("Could not obtain the latest version of OpenCRS!")
        logger.debug(f"FAILED TO OBTAIN OPENCRS VERSION\n{e}")

    # Check NOAA status
    if noaa.ok:
        logger.info("NWS Api is up!")
        asyncio.run(main())
    else:
        logger.critical("Couldn't get a 200 from NWS! Check to see if you're connected to the internet.")
