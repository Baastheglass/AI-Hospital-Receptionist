import base64
import numpy as np

def base64_decode_audio(encoded_str):
    try:
        pcm_bytes = base64.b64decode(encoded_str)
        int16_array = np.frombuffer(pcm_bytes, dtype=np.int16)
        float32_array = int16_array.astype(np.float32) / 32767.0
        return float32_array
    except Exception as e:
        print(f"Error decoding audio: {e}")
        return np.array([], dtype=np.float32)

def reconstruct_audio(audio_chunks):
    if not audio_chunks or len(audio_chunks) == 0:
        print("No audio chunks to reconstruct")
        return np.array([], dtype=np.float32)
        
    decoded_chunks = []
    for chunk in audio_chunks:
        try:
            decoded = base64_decode_audio(chunk)
            if len(decoded) > 0:  # Only add non-empty chunks
                decoded_chunks.append(decoded)
        except Exception as e:
            print(f"Error decoding chunk: {e}")
            continue
    
    if not decoded_chunks:
        print("No valid audio chunks after decoding")
        return np.array([], dtype=np.float32)
    
    full_audio = np.concatenate(decoded_chunks)
    return full_audio

# Add this function for the transcription.py file
def base64_encode_audio(float32_array):
    if len(float32_array) == 0:
        print("Empty audio data, cannot encode")
        return ""
        
    try:
        # Ensure the audio is properly clipped
        clipped = np.clip(float32_array, -1.0, 1.0)
        
        # Convert to int16 (PCM format)
        int16_data = np.int16(clipped * 32767)
        
        # Convert to bytes
        pcm_bytes = int16_data.tobytes()
        
        # Encode to base64
        encoded = base64.b64encode(pcm_bytes).decode('ascii')
        
        return encoded
    except Exception as e:
        print(f"Error encoding audio: {e}")
        return ""