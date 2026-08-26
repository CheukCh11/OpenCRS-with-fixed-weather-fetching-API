import os
import subprocess
import platform
import re

def apply_pronunciation_dict(text):
    """Reads pronunciationfix.dic and dynamically replaces abbreviations."""
    dic_path = "pronunciationfix (1).dic"
    if not os.path.exists(dic_path):
        return text

    with open(dic_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines or lines without an equals sign
            if '=' not in line or line.startswith('#'):
                continue

            key, val = line.split('=', 1)
            if not key:
                continue

            # If the key is just letters/numbers (like "mph" or "tstm"), use word boundaries
            # This prevents replacing letters inside of other words.
            if re.match(r'^[A-Za-z0-9_]+$', key):
                pattern = r'\b' + re.escape(key) + r'\b'
                # IGNORECASE ensures "tstm" catches the capitalized "TSTM" in NWS texts
                text = re.sub(pattern, val, text, flags=re.IGNORECASE)
            else:
                # If the key contains punctuation (like "HAZARD...60" or "/"), do a standard replace
                pattern = re.escape(key)
                text = re.sub(pattern, val, text, flags=re.IGNORECASE)

    return text

def clean_text_for_dectalk(text):
    """Cleans up formatting artifacts without destroying section text."""
    # Convert brackets to parentheses to prevent DECtalk command injection
    text = text.replace('[', '(').replace(']', ')')
    
    # Apply user's custom dictionary overrides
    text = apply_pronunciation_dict(text)
    
    # Clean up excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def dectalk(r=250, v='p', filelocation="../output.txt", **kwargs):
    print("Speaking via DECtalk...")
    
    if filelocation.startswith("../"):
        filelocation = filelocation[3:]
        
    abs_file_location = os.path.abspath(filelocation)
    
    if not os.path.exists(abs_file_location):
        print(f"Error: {abs_file_location} not found.")
        return

    with open(abs_file_location, "r", encoding="utf-8") as f:
        raw_text = f.read()
        
    clean_text = clean_text_for_dectalk(raw_text)
    
    if str(v).startswith('[:'):
        voice_code = str(v)
    else:
        voice_code = f"[:rate {r}][:n{v}]"
    
    spoken_text = f"{voice_code}\n{clean_text}"
    
    # First, define the directory
    dectalk_dir = os.path.join(os.getcwd(), "dectalk")
    
    # Second, construct the full, absolute path to the executable
    say_exe_path = os.path.join(dectalk_dir, "say.exe")
    
    # Third, use the absolute path in the command
    cmd = ["wine", say_exe_path] if platform.system() != "Windows" else [say_exe_path]

    try:
        process = subprocess.Popen(
            cmd,
            cwd=dectalk_dir, 
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(input=spoken_text.encode('utf-8'))
        
        if process.returncode != 0:
            print(f"DECtalk Error: {stderr.decode('utf-8', errors='ignore')}")
            
    except Exception as e:
        print(f"Failed to run DECtalk: {e}")
