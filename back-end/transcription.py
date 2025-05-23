import json
import websocket
import time
import base64
import os
import struct
from dotenv import load_dotenv
import threading
import asyncio
from reconstruct_audio import reconstruct_audio
from rag import rag2
from threading import Lock
from utils import (
    amplify_audio,
    base64_encode_audio,
    float_to_16bit_pcm
)

#LOG_FILENAME = "logs.txt"
    
class OpenAITranscriber:
    openai_ws = None
    _ws_lock = Lock()
    openai_thread = None
    
    def __init__(self, client_websocket):
        self.client_websocket = client_websocket
        self.stream_active = False
        self.sent_audio = False
        self.current_audio = []
        self.sent_rag = False
        self._sent_rag_lock = Lock()
        self.item_ids = []
        self.processed_message_ids = set()
        self.processed_transcripts = set()
        self.processed_audio_responses = set()
        self.last_transcript = None
        

        # file = open("logs.txt", "w")
        # file.write("")
        # file.close()
        
        load_dotenv()
        self.initialize_websockets()
        
    async def test(self):
        message = {
            "event_type": "checking connectivity",
            "event_data": "connection established"
        }
        await self.client_websocket.send_json(message)

    def is_openai_connected(self):
        return (self.openai_ws and hasattr(self.openai_ws, 'sock') 
            and self.openai_ws.sock and self.openai_ws.sock.connected)
        
    def initialize_websockets(self):
        try:
            OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
            
            if not OPENAI_API_KEY:
                raise ValueError("Missing OPENAI_API_KEY")
            
            headers = ["Authorization: Bearer " + OPENAI_API_KEY, "OpenAI-Beta: realtime=v1"]
            
            self.openai_ws = websocket.WebSocketApp(
                url="wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview",
                header=headers,
                on_open=self.on_openai_open,
                on_message=self.on_openai_message,
                on_error=self.on_error,
                on_close=self.on_openai_close
            )
            
            self.openai_thread = threading.Thread(
                target=self.openai_ws.run_forever,
                daemon=True
            )
            self.openai_thread.start()
            time.sleep(1)  # Give time for connection
        except Exception as e:
            pass
            #print(f"WebSocket initialization failed: {e}")
            #log(f"WebSocket initialization failed: {e}", LOG_FILENAME)    
        # Add these new methods for better connection management
    
    def on_openai_close(self, ws, close_status_code, close_msg):
        pass
        #print(f"OpenAI WebSocket closed: {close_status_code} - {close_msg}")
        #log(f"OpenAI WebSocket closed: {close_status_code} - {close_msg}", LOG_FILENAME)
        
    def on_client_close(self, ws, close_status_code, close_msg):
        pass
        #print(f"Client WebSocket closed: {close_status_code} - {close_msg}")
        #log(f"Client WebSocket closed: {close_status_code} - {close_msg}", LOG_FILENAME)
        
    def on_client_open(self, ws):
        pass
        #print("Client WebSocket connection established")
        #log("Client WebSocket connection established", LOG_FILENAME)   

    def set_client_websocket(self, client_websocket):
        self.client_websocket = client_websocket

    def process_audio_chunk(self, indata, frames, time, status):
        if status:
            pass
            #print("Status:", status)
            #log("Status:" + str(status), LOG_FILENAME)
        if not self.stream_active or self.openai_ws is None:
            return
            
        audio_chunk = indata[:, 0]  # if mono, or pick a single channel
        amplified_chunk = amplify_audio(audio_chunk)
            
        self.send_audio_to_openai(amplified_chunk)
    
    def send_audio_to_openai(self, base64_audio):
        #log("\n>> Sending audio to openai\n\n", LOG_FILENAME)
        with self._ws_lock:
            try:
                if not self.is_openai_connected():
                    #print("OpenAI socket not connected, cannot send audio")
                    return False

                event = {
                    "type": "input_audio_buffer.append",
                    "audio": base64_audio
                }
                self.openai_ws.send(json.dumps(event))
                return True
                
            except Exception as e:
                #print(f"Error sending audio to OpenAI: {str(e)}")
                #log(f"Error sending audio to OpenAI: {str(e)}", LOG_FILENAME)
                return False
                            
    def on_openai_open(self, ws):
        pass
        #print("Connected to OpenAI server.")
        #log("Connected to OpenAI server.", LOG_FILENAME)
                
        
    def websocket_working(self, socket_name):
        if(socket_name == "client"):
            return self.client_websocket is not None and self.client_websocket.sock is not None and self.client_websocket.sock.connected
        elif(socket_name == "openai"):
            return self.openai_ws is not None and self.openai_ws.sock is not None and self.openai_ws.sock.connected
        
    def on_openai_message(self, ws, message):
        data = json.loads(message)
        
        #print("Raw message received from OpenAI")
        #log("Raw message received from OpenAI", LOG_FILENAME)
        ##print(data)
        #log(data, LOG_FILENAME)
         # Create event loop if none exists
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if(data['type'] == "session.created"):
            event = {
                "type": "session.update",
                "session": {
                    "instructions": "Your job is to transcript audio you're given, and create speech of text you're given.",
                    "input_audio_transcription": {
                        "model": "whisper-1",
                        "language": "en"
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500,
                        "create_response": False,
                        "interrupt_response": False
                    },
                    "voice": "ballad"
                }
            }
            if(self.websocket_working("openai")):
                self.openai_ws.send(json.dumps(event))
            
        elif(data['type'] == "conversation.item.input_audio_transcription.completed"):
            transcript = data['transcript']
            item_id = data['item_id']
            event = rag2(transcript)
            self.openai_ws.send(json.dumps(event))
            
        elif(data['type'] == "response.text.delta"):
            pass
            #print(data)
            #log(data, LOG_FILENAME)
            
        elif(data['type'] == "response.audio.delta"):
            #print(data)
            #log(data, LOG_FILENAME)
            self.current_audio.append(data['delta'])
            #log("Data added into array", LOG_FILENAME)
            
        elif(data['type'] == "response.audio.done"): #and self.sent_audio == True):
            if(len(self.current_audio) >= 0):
                #log("Appropriate length", LOG_FILENAME)
                to_send_audio = reconstruct_audio(self.current_audio)
                #print(to_send_audio)
                if (len(to_send_audio) > 0):
                    #log(f"Audio data length: {len(to_send_audio)}", LOG_FILENAME)
                    base_64_audio = base64_encode_audio(to_send_audio) #encoding before sending
                    if base_64_audio:
                        loop.run_until_complete(self.send_to_client(base_64_audio))
                        #print("Message sent")
                        #log("Message sen", LOG_FILENAME)
                    else:
                        pass
                        #log("Failed to encode audio", LOG_FILENAME)
                else:
                    pass
                    #log("Reconstructed audio is empty", LOG_FILENAME)
                self.current_audio = []
            else:
                #log("Insufficient length", LOG_FILENAME)
                return
                
        elif(data['type'] == "response.done"):
            try:
                if(data['metadata']['topic'] == "rag"):
                    rag_response = data['response']['output']['content']['text']
                    item_id = data['response']['output']['id']
                    #log(item_id, LOG_FILENAME)
            except:
                pass
        else:
            pass
            #print("Received event:", json.dumps(data, indent=2) + '\n')
            #log("Received event:" + json.dumps(data, indent=2) + '\n', LOG_FILENAME)
                
    def on_error(self, ws, error):
        if isinstance(error, Exception):
            error_msg = str(error)
        else:
            error_msg = error
        #print("Error:", error_msg)
        #log("Error:" + error_msg, LOG_FILENAME)
    
    async def send_to_client(self, base_64_audio):
        if not base_64_audio:
            #log("Attempted to send empty audio data", LOG_FILENAME)
            return
        message = {
                    "event_type": "audio_response_transmitting",
                    "event_data": base_64_audio
                }
        try:
            await self.client_websocket.send_json(message)    
        except Exception as e:
            pass
            #print(e)
            #log(str(e), LOG_FILENAME)
        
    def stop_transcription(self):
        self.stream_active = False
        
        if self.openai_ws:
            self.openai_ws.close()
            self.openai_ws = None
            
        return True
    
    def get_voice_output(self, text):
        event = {
            "type": "session.update"
        } 
        self.openai_ws.send(json.dumps(event))       
        
if __name__ == "__main__":
    #print("Entering main function")
    #log("Entering main function", LOG_FILENAME)
    transcriber = OpenAITranscriber()
    # Keep the main thread alive to prevent immediate exit
    try:
        #print("Transcription running. Press Ctrl+C to exit...")
        #log("Transcription running. Press Ctrl+C to exit...", LOG_FILENAME)
        while True:
            time.sleep(2.5)
    except KeyboardInterrupt:
        #print("Stopping transcription...")
        #log("Stopping transcription...", LOG_FILENAME)
        transcriber.stop_transcription()
