# pylistener
Simple Python script that "listens" to ambient noise and records any sounds over a specified amplitude.

This script is designed to run on a Raspberry Pi with a USB microphone (or webcam with built-in mic).  It saves detected sounds as .wav files, starting 4 seconds before the detected sound and continuing until 4 seconds of silence.

The script requires PyAudio (https://people.csail.mit.edu/hubert/pyaudio/) and is based on the script by Russell Borogove (http://stackoverflow.com/questions/4160175/detect-tap-with-pyaudio-from-live-mic).
