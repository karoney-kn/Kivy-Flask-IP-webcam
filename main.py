import os
import sys
import cv2
import time
import signal
import pyaudio
import requests
import threading
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.uix.screenmanager import Screen
from flask import Flask,Response,render_template,send_from_directory,redirect,url_for,request,jsonify


Window.size = (360,820)
Window.fullscreen = False
Builder.load_file('kvfserv.kv')

fonts_path = "assets/"

fonts = [
    {
        "name": "Nasa",
        "fn_regular": fonts_path + "nasalization.ttf",
        "fn_bold": fonts_path + "nasalization.ttf",
    },
    {
        "name": "Droidsans",
        "fn_regular": fonts_path + "DroidSansMono.ttf",
        "fn_bold": fonts_path + "DroidSansMono.ttf",
    },
]


class KvFservMain:
    def __init__(self):
        self.front_camera = 0
        self.back_camera = 1
        self.camera_index = self.front_camera
        self.web_cam = cv2.VideoCapture(self.camera_index)
        self.audio_format = pyaudio.paInt16
        self.audio_channels = 2
        self.audio_rate = 44100
        self.chunk_size = 1024
        self.audio_stream = pyaudio.PyAudio()
        self.streaming = True
        self.mute = False

    def run_web_server(self):
        kvfserv_webcam = Flask(__name__)

        def initialize_camera():
            if not self.web_cam.isOpened():
                raise Exception("Error: Camera Not Available.")

        def get_camera_type():
            if self.camera_index == 0:
                return "Front Camera"
            else:
                return "Back Camera"

        def generate_video_feed():
            while True:
                ret, frame = self.web_cam.read()
                if not ret:
                    self.web_cam.release()
                    break
                frame = cv2.flip(frame, 1)  # Flip horizontally
                #Convert the frame to JPEG
                _, jpeg = cv2.imencode('.jpg', frame)
                frame_bytes = jpeg.tobytes()
                yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n\r\n')

        def genHeader(sampleRate, bitsPerSample, channels):
            datasize = 2000 * 10 ** 6
            o = bytes("RIFF", 'ascii')
            o += (datasize + 36).to_bytes(4, 'little')
            o += bytes("WAVE", 'ascii')
            o += bytes("fmt ", 'ascii')
            o += (16).to_bytes(4, 'little')
            o += (1).to_bytes(2, 'little')
            o += (channels).to_bytes(2, 'little')
            o += (sampleRate).to_bytes(4, 'little')
            o += (sampleRate * channels * bitsPerSample // 8).to_bytes(4, 'little')
            o += (channels * bitsPerSample // 8).to_bytes(2, 'little')
            o += (bitsPerSample).to_bytes(2, 'little')
            o += bytes("data", 'ascii')
            o += (datasize).to_bytes(4, 'little')
            return o

        def stream_audio():
            bits_per_sample = 16
            wav_header = genHeader(self.audio_rate, bits_per_sample, 2)
            stream = self.audio_stream.open(format=self.audio_format,
                    channels=self.audio_channels,
                    rate=self.audio_rate,
                    input=True,
                    frames_per_buffer=self.chunk_size)
            first_run = True
            while True:
    
                if first_run:
                    data = wav_header + stream.read(self.chunk_size)
                    first_run = False
                else:
                    data = stream.read(self.chunk_size)
                yield data


        @kvfserv_webcam.route('/video_feed')
        def video_feed():
            return Response(generate_video_feed(), mimetype='multipart/x-mixed-replace; boundary=frame')

        @kvfserv_webcam.route("/audio")
        def audio():
            return Response(stream_audio(), mimetype="audio/x-wav")

        @kvfserv_webcam.route('/')
        def index():
            camera_type = get_camera_type()
            try:
                initialize_camera()
            except Exception as e:
                return render_template('index.html', camera_type=camera_type, error_message=str(e))
            return render_template('index.html', camera_type=camera_type,error_message=None)

        @kvfserv_webcam.route('/assets/<path:filename>')
        def serve_staticfiles(filename):
            return send_from_directory(os.path.join(kvfserv_webcam.root_path, 'assets'), filename)

        @kvfserv_webcam.route('/switch_camera', methods=['POST'])
        def switch_camera():
            self.web_cam.release()
            self.camera_index = 1 if self.camera_index == 0 else 0
            self.web_cam = cv2.VideoCapture(self.camera_index)
            time.sleep(0.25)
            return redirect(url_for('index'))

        kvfserv_webcam.run(host='0.0.0.0', port=5000, threaded=True,use_reloader=False)


class KvFservHome(App):
    event_clock = None
    def __init__(self,**kwargs):
        super(KvFservHome, self).__init__(**kwargs)
        self.title = "Kivy-Flask-IPWebcam"
        self.icon = "assets/icon.png"
        for font in fonts:
            LabelBase.register(**font)
        self.camera_stream = KvFservMain()

    def build(self):
        self.main_screen = MainScreen()
        return self.main_screen

    def on_start(self):
        self.flask_serverthread = threading.Thread(target=self.camera_stream.run_web_server)
        self.flask_serverthread.daemon = True
        self.flask_serverthread.start()

    def on_stop(self):
        print("Shutting down...")
        # Perform cleanup before the Kivy app completely shuts down
        signal.signal(signal.SIGINT, self.flask_server_shutdown_signal())
        signal.signal(signal.SIGTERM, self.flask_server_shutdown_signal())

        super().on_stop()

    def flask_server_shutdown_signal(self):
        if self.camera_stream.web_cam.isOpened():
            self.camera_stream.web_cam.release()
        # Send the shutdown signal to the Flask thread
        sys.exit(0)
        

class MainScreen(Screen):
    pass

if __name__ == '__main__':
    kvfserv = KvFservHome()
    kvfserv.run()


