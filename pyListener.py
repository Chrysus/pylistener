#!/usr/bin/python

# open a microphone in pyAudio and listen for sounds

import pyaudio
import struct
import math
import time
import datetime
import wave


INITIAL_TAP_THRESHOLD = 0.005
RECORDING_NOISE_THRESHOLD = 0.004

FORMAT = pyaudio.paInt16 
SHORT_NORMALIZE = (1.0 / 32768.0)
CHANNELS = 2
RATE = 44100  
INPUT_BLOCK_TIME = 0.05
INPUT_FRAMES_PER_BLOCK = int(RATE * INPUT_BLOCK_TIME)

# if we get this many noisy blocks in a row, increase the threshold
OVERSENSITIVE = 15.0 / INPUT_BLOCK_TIME                    

# if we get this many quiet blocks in a row, decrease the threshold
UNDERSENSITIVE = 120.0 / INPUT_BLOCK_TIME 

# if the noise was longer than this many blocks, it's not a 'tap'
MAX_TAP_BLOCKS = 0.15 / INPUT_BLOCK_TIME

# Circular Buffer
CIRCULAR_BUFFER_SIZE = int(4 / INPUT_BLOCK_TIME)

# Recording Buffer
RECORDING_BUFFER_TIMEOUT = 4 / INPUT_BLOCK_TIME


def get_rms( block ):
    # RMS amplitude is defined as the square root of the 
    # mean over time of the square of the amplitude.
    # so we need to convert this string of bytes into 
    # a string of 16-bit samples...

    # we will get one short out for each 
    # two chars in the string.
    count = len(block) / 2
    format = "%dh" % (count)
    shorts = struct.unpack( format, block )

    # iterate over the block.
    sum_squares = 0.0
    for sample in shorts:
        # sample is a signed short in +/- 32768. 
        # normalize it to 1.0
        n = sample * SHORT_NORMALIZE
        sum_squares += n*n

    return math.sqrt( sum_squares / count )


class NoiseListener(object):
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self.audio_stream = self.open_mic_stream()
        self.noise_threshold = INITIAL_NOISE_THRESHOLD
        self.cur_noise_start_time = None
        self.cur_noise_end_time = None
        self.quietcount = 0
        self.noisycount = 0
        self.errorcount = 0
        self.auto_adjust = False

        self.noise_circular_buffer = [None] * CIRCULAR_BUFFER_SIZE
        self.noise_circular_buffer_index = 0
        self.cur_noise_buffer = []
        self.cur_noise_buffer_quiet_count = 0
        self.recording = False


    def stop(self):
        self.audio_stream.close()

    def find_input_device(self):
        device_index = None            
        for i in range( self.pa.get_device_count() ):     
            devinfo = self.pa.get_device_info_by_index(i)   
            print( "Device %d: %s"%(i,devinfo["name"]) )

            for keyword in ["mic","input"]:
                if keyword in devinfo["name"].lower():
                    print( "Found an input: device %d - %s"%(i,devinfo["name"]) )
                    device_index = i
                    return device_index

        if device_index == None:
            print( "No preferred input found; using default input device." )

        return device_index


    def open_mic_stream( self ):
        device_index = self.find_input_device()

        stream = self.pa.open(   format = FORMAT,
                                 channels = CHANNELS,
                                 rate = RATE,
                                 input = True,
                                 input_device_index = device_index,
                                 frames_per_buffer = INPUT_FRAMES_PER_BLOCK)

        return stream


    def noiseDetected(self):
        timestamp = time.time()
        timestamp_string = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        print timestamp_string + "     " + "Noise!"

    
    def startRecording(self):
        print "Recording - Start"
        self.cur_noise_buffer = []

        # Copy the circular buffer into the recording buffer
        start_index = (self.noise_circular_buffer_index + 1) % CIRCULAR_BUFFER_SIZE
        end_index = self.noise_circular_buffer_index
        #if end_index < 0:
        #    end_index = (CIRCULAR_BUFFER_SIZE - 1)

        index = start_index
        while index != end_index:
            block = self.noise_circular_buffer[index]
            if None != block:
                self.cur_noise_buffer.append(block)
#                for block_data in block:
#                    self.cur_noise_buffer.append(block_data)
#                    pass #this isn't working
            index = (index + 1) % CIRCULAR_BUFFER_SIZE

        #if None != self.noise_circular_buffer[end_index]:
        #    for block_data in self.noise_circular_buffer[end_index]:
        #        self.cur_noise_buffer.append(block_data)

        self.recording = True

        # TEST
        self.noise_threshold = RECORDING_NOISE_THRESHOLD


    def updateRecording(self, block):
        #print "Recording"
        self.cur_noise_buffer.append(block)


    def stopRecording(self):
        print "Recording - Stop"
        self.recording = False
        self.saveAudioFile()

        # TEST
        self.noise_threshold = INITIAL_NOISE_THRESHOLD


    def addBlockToBuffer(self, block):
        self.cur_noise_buffer.append(block)

        
    def addBlockToCircularBuffer(self, block):
        self.noise_circular_buffer[self.noise_circular_buffer_index] = block
        self.noise_circular_buffer_index = (self.noise_circular_buffer_index + 1) % CIRCULAR_BUFFER_SIZE


    def saveAudioFile(self):
        WAVE_OUTPUT_FILENAME = "listener_test.wav"
        filename = time.strftime("%Y-%m-%d_%H%M%S") + ".wav"
        wf = wave.open( filename, 'wb' )
        wf.setnchannels( CHANNELS )
        wf.setsampwidth( self.pa.get_sample_size(FORMAT) )
        wf.setframerate( RATE )
        wf.writeframes(b''.join(self.cur_noise_buffer))
        wf.close()


    def listen(self):
        try:
            block = self.audio_stream.read(INPUT_FRAMES_PER_BLOCK)

            if None != block:
                self.addBlockToCircularBuffer( block )

                if True == self.recording:
                    self.updateRecording( block )
        except IOError, e:
            # d'oh!
            self.errorcount += 1
            print( "(%d) Error recording: %s"%(self.errorcount,e) )
            self.noisycount = 1
            return

        amplitude = get_rms( block )
        if amplitude > self.noise_threshold:
            # noisy block
            if False == self.recording:
                self.startRecording()

            self.cur_noise_buffer_quiet_count = 0

            self.quietcount = 0
            self.noisycount += 1
            if self.noisycount > OVERSENSITIVE and self.auto_adjust:
                # turn down the sensitivity
                self.noise_threshold *= 1.1
        else:            
            # quiet block.
            self.cur_noise_buffer_quiet_count += 1

            if True == self.recording and RECORDING_BUFFER_TIMEOUT < self.cur_noise_buffer_quiet_count:
                self.stopRecording()

            if 1 <= self.noisycount <= MAX_TAP_BLOCKS:
                self.noiseDetected()
            self.noisycount = 0
            self.quietcount += 1
            if self.quietcount > UNDERSENSITIVE and self.auto_adjust:
                # turn up the sensitivity
                self.noise_threshold *= 0.9



if __name__ == "__main__":
    nl = NoiseListener()
    
    #for i in xrange(1000):
    while True:
        nl.listen()
