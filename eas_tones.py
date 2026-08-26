import wave
import struct
import math
import os
import subprocess
import platform

SAMPLE_RATE = 44100
MARK_FREQ = 2083.3333  # Logic 1 (4 cycles per bit)
SPACE_FREQ = 1562.5000  # Logic 0 (3 cycles per bit)
BAUD_RATE = 520.833333  # 520.83 baud (~1.92ms per bit)
SAMPLES_PER_BIT = int(SAMPLE_RATE / BAUD_RATE)  # ~84.67 samples/bit

def generate_sine_samples(freq, duration_sec, amplitude=0.5):
    """Generates 16-bit mono PCM sine wave audio frames."""
    num_samples = int(SAMPLE_RATE * duration_sec)
    frames = bytearray()
    for i in range(num_samples):
        t = float(i) / SAMPLE_RATE
        sample_val = int(amplitude * 32767.0 * math.sin(2.0 * math.pi * freq * t))
        frames.extend(struct.pack('<h', sample_val))
    return frames

def generate_1050hz_tone(duration_sec=10.0, amplitude=0.6, output_path="sounds/1050hz.wav"):
    """Generates 1050 Hz NWR Warning/Attention Tone WAV file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    frames = generate_sine_samples(1050.0, duration_sec, amplitude)
    
    with wave.open(output_path, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(frames)
        
    print(f"Generated 1050 Hz Attention Tone ({duration_sec}s): {output_path}")
    return output_path

def _byte_to_afsk_samples(b, phase=0.0, amplitude=0.5):
    """Converts a single byte into 8 AFSK bits (LSB first) audio samples."""
    frames = bytearray()
    current_phase = phase
    
    for bit_idx in range(8):
        bit = (b >> bit_idx) & 1
        freq = MARK_FREQ if bit == 1 else SPACE_FREQ
        
        for _ in range(SAMPLES_PER_BIT):
            sample_val = int(amplitude * 32767.0 * math.sin(current_phase))
            frames.extend(struct.pack('<h', sample_val))
            current_phase += 2.0 * math.pi * freq / SAMPLE_RATE
            
    return frames, current_phase

def _string_to_afsk_burst(text, amplitude=0.5):
    """Converts SAME preamble + string into an AFSK audio bytearray."""
    # 16 preamble bytes of 0xAB (10101011)
    data_bytes = bytes([0xAB] * 16) + text.encode('ascii')
    frames = bytearray()
    phase = 0.0
    
    for b in data_bytes:
        chunk_frames, phase = _byte_to_afsk_samples(b, phase=phase, amplitude=amplitude)
        frames.extend(chunk_frames)
        
    return frames

def generate_same_header(same_str="ZCZC-EAS-RWT-036061+0030-2361600-KOKX/NWS-", output_path="sounds/same_header.wav", amplitude=0.5):
    """Generates standard SAME header AFSK audio burst (repeated 3 times with 1s pauses)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    single_burst = _string_to_afsk_burst(same_str, amplitude=amplitude)
    silence_1s = bytearray(b'\x00\x00' * int(SAMPLE_RATE * 1.0))
    
    total_frames = bytearray()
    for i in range(3):
        total_frames.extend(single_burst)
        if i < 2:
            total_frames.extend(silence_1s)
            
    with wave.open(output_path, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(total_frames)
        
    print(f"Generated SAME Header Audio: {output_path}")
    return output_path

def generate_eom_tones(output_path="sounds/eom.wav", amplitude=0.5):
    """Generates standard SAME End of Message (EOM / NNNN) bursts."""
    return generate_same_header(same_str="NNNN", output_path=output_path, amplitude=amplitude)

def play_audio(wav_file_path):
    """Plays WAV audio file natively on macOS using afplay."""
    if not os.path.exists(wav_file_path):
        print(f"Audio file not found: {wav_file_path}")
        return
        
    system_name = platform.system()
    if system_name == "Darwin":
        subprocess.run(["afplay", wav_file_path])
    elif system_name == "Windows":
        import winsound
        winsound.PlaySound(wav_file_path, winsound.SND_FILENAME)
    else:
        # Linux fallback using aplay or paplay
        subprocess.run(["aplay", wav_file_path])

if __name__ == '__main__':
    # Test generation
    generate_1050hz_tone(10.0)
    generate_same_header("ZCZC-EAS-RWT-036061+0030-2361600-KOKX/NWS-")
    generate_eom_tones()
