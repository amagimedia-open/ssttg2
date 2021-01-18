#+---------+
#| IMPORTS |
#+---------+

from __future__ import division
import re
import os
import sys
import time 
import threading
import queue
import traceback
import getopt
import stat
import configparser
from   collections import OrderedDict

import google
from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
#from difflib import SequenceMatcher

#+-----------------------------+
#| INI FILE SECTIONS AND NAMES |
#+-----------------------------+

#names under the section FILES in the .ini file

G_FILES_SECTION_NAME="FILES"
G_INPUT_AUDIO_PATH_CFG_NAME="input_audio_path"
G_OUTPUT_SRT_PATH_CFG_NAME="output_srt_path"
G_GCP_AUTH_PATH_CFG_NAME="gcp_auth_path"
G_PHRASES_PATH_CFG_NAME="phrases_path"

#names under the section TRANSLATION in the .ini file

G_TRANSLATION_SECTION_NAME="TRANSLATION"
G_TIMEOUT_SECONDS_CFG_NAME = "timeout_seconds"
G_REPEAT_SUB_THREASHOLD_MS_CFG_NAME = "repeat_sub_threashold_ms"
G_WRITE_AFTER_CHARACTERS_RECVD_CFG_NAME = "write_after_characters_recvd"
G_MAX_SUB_CHARS_CFG_NAME = "max_sub_chars"
G_STREAMING_LIMIT_CFG_NAME="streaming_limit"
G_MIN_SUB_DURATION_MS_CFG_NAME="min_sub_duration_ms"
G_MAX_SUB_DURATION_MS_CFG_NAME="max_sub_duration_ms"

#+------------------------------+
#| DEFAULT CONFIGURATION VALUES |
#+------------------------------+

#TODO: These can be directly read from an configparser object

# Fixed Audio recording parameters
G_BYTE_PER_SAMPLE = 2
G_AUD_SAMPLING_RATE = 16000
G_CHUNK_MS = 32
G_CHUNK_SIZE_BYTES = int(G_AUD_SAMPLING_RATE / 1000 * G_CHUNK_MS * G_BYTE_PER_SAMPLE)

# Fixed Input packet parameters
G_AUDIO_HEADER_LEN = 14 # 4 sync + 8 pts + 2 len

# Default Translation process parameters
G_TIMEOUT_SECONDS = 3
G_TIMEOUT_MSECONDS = G_TIMEOUT_SECONDS*1000
G_REPEAT_SUB_THREASHOLD_MS = 1000
G_WRITE_AFTER_CHARACTERS_RECVD = 150
G_MAX_SUB_CHARS = 30
G_STREAMING_LIMIT = 240000 # 280 seconds, as 300 is max limit
G_MIN_SUB_DURATION_MS = 400 # ms
G_MAX_SUB_DURATION_MS = 4000 # ms

# Computed Translation process parameters
G_MAX_AUDIO_BUFFER = 1000 / G_CHUNK_MS # 5 sec

#+-----------+
#| FUNCTIONS |
#+-----------+

#def similar(a, b):
#    return SequenceMatcher(None, a, b).ratio()

def milliseconds_to_HMS (ms):
    ms -= 1000
    msp = ms % 1000
    ms /= 1000
    ss = ms % 60
    ms /= 60
    mm = ms % 60
    ms /= 60
    hh = ms
    
    #ret = time.strftime('%H:%M:%S', time.gmtime(ms))
    # %07d, as UINT64 MAX / NANOSECOND / 60 / 60 is max 7 digits.
    ret = "%07d:%02d:%02d" %(hh,mm,ss)
    ret += ",%03d" %msp
    return ret

def get_current_time():
    """Return Current Time in MS."""

    return int(round(time.time() * 1000))

class StreamDataStructure ():
    def __init__ (self):
        self.stream_time = get_current_time ()
        self.restart_counter = 0
        self.consumed_ms = 0
        self.last_iter_consumed_ms = 0
        self.max_sent_audio_q_len = 500 / G_CHUNK_MS
        self.sent_audio_q = queue.Queue ()
        self.sent_q_head_pts = 0
        self.last_sub_pts = 0
        self.old_data_sent_ms = 0
        self.audio_pts_map = OrderedDict () # 0_pts:actual:pts
        self.audio_pts_map_lock = threading.Lock ()

    def get_mapped_audio_pts (self, inp_pts):
        self.audio_pts_map_lock.acquire()
        #tmp = list(self.audio_pts_map.keys ())
        #print (f"$$$ Delay = {tmp[-1]-tmp[0]}")
        key = min(self.audio_pts_map.keys (), key=lambda x:abs(x-inp_pts))
        for _key in list(self.audio_pts_map.keys()):
            if _key < key:
                del self.audio_pts_map[_key]

        self.audio_pts_map_lock.release()
        #print (f"$$$ ----{self.audio_pts_map[key]}  ---- {self.audio_pts_map[key] + inp_pts - key}")
        return self.audio_pts_map[key] + inp_pts - key


    def push_to_sent_q (self, data):
        self.sent_audio_q.put (data)
        while self.sent_audio_q.qsize () > self.max_sent_audio_q_len:
            self.sent_audio_q.get ()
            self.sent_q_head_pts += G_CHUNK_MS

    def get_data_from_pts (self):
        data = None
        pts = self.last_sub_pts + (self.restart_counter-1) * G_STREAMING_LIMIT
        hpts = self.sent_q_head_pts
        tpts = hpts + (self.sent_audio_q.qsize () * G_CHUNK_MS)
        print (f"get_data_from_pts ,pts={pts} hpts={hpts} tpts={tpts} == {pts < hpts or pts > tpts and tpts-pts >= G_CHUNK_MS}")
        if pts < hpts or pts > tpts or (tpts-pts) < G_CHUNK_MS:
            return data

        # Drain extra data
        while self.sent_q_head_pts < pts:
            self.sent_audio_q.get ()
            self.sent_q_head_pts += G_CHUNK_MS 

        # Drain data to be resent
        data_l = []
        while self.sent_audio_q.qsize () > 0:
            data = self.sent_audio_q.get ()
            data_l.append (data)
            self.sent_q_head_pts += G_CHUNK_MS 
            #print (f"Getting a CHUNKKKKKKKKKKK {len(data)}")

        if data_l:
            data = b''.join(data_l)
            
        self.old_data_sent_ms = len(data) / G_BYTE_PER_SAMPLE / (G_AUD_SAMPLING_RATE/1000)
        print (f"Resending {self.old_data_sent_ms} ms data")

        return data
        

class myThread (threading.Thread):
    def __init__(self, threadID, name, q,srt_fname):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.q = q
        self.exit_flag = False
        self.srt_fname = srt_fname
        self.last_transcription = ""
        self.last_read_pos = 0
        self.srt_count = 0
        self.pos_pts_map = OrderedDict ()#{pos:timestamp}
        self.last_srt_sub = []#[tcin,tcout,text]
        self.last_transcript_len = 0 #used for adding pos-time to map
        self.last_sub_end_pts = 0
  
    def srt_writer (self, text, tc_in, duration_ms):
        with open (self.srt_fname, "w") as fp:
            self.srt_count += 1
            srt_text = f"{self.srt_count}\n"
            #fp.write (f"{self.srt_count}\n")
            if False:#len(self.last_srt_sub) > 0 and (tc_in-self.last_srt_sub[1] < G_REPEAT_SUB_THREASHOLD_MS):
                #fp.write (f"{milliseconds_to_HMS (self.last_srt_sub[1])} --> {milliseconds_to_HMS (tc_in+duration_ms)}\n")
                #fp.write (self.last_srt_sub[2].strip() + "\n")
                srt_text += f"{milliseconds_to_HMS (self.last_srt_sub[1])} --> {milliseconds_to_HMS (tc_in+duration_ms)}\n"
                srt_text += self.last_srt_sub[2].strip() + "\n"
            else:
                #fp.write (f"{milliseconds_to_HMS (tc_in)} --> {milliseconds_to_HMS (tc_in+duration_ms)}\n")
                srt_text += f"{milliseconds_to_HMS (tc_in)} --> {milliseconds_to_HMS (tc_in+duration_ms)}\n"
            #fp.write (text.strip() + "\n\n")
            srt_text += text.strip() + "\n\n"
            #fp.write (str(srt_text)+"\0")
            fp.write (srt_text.encode ('ascii', 'ignore').decode('ascii').upper()+"\0")
            print (srt_text.encode('utf-8'), flush=True)
            self.last_srt_sub = [tc_in, tc_in+duration_ms, text]

    def align_to_next_word (self, cur_transcription, is_timeout=False):
        last_len = len(self.last_transcription)
        if len (cur_transcription) > last_len or is_timeout:
            if cur_transcription[:last_len] == self.last_transcription:
                # Equal Case
                #print ("Equal case")
                pass
            elif cur_transcription[self.last_read_pos] == " ":
                #print ("There is space anyway")
                pass
            else:# similar (cur_transcription[:last_len], self.last_transcription) > 0.9:

                i_in_new = -1
                j=0
                for i in range (last_len-1, -1, -1):
                    if self.last_transcription[i] ==" ":
                        j=j+1
                    if j==3:
                        break

                if i != -1:
                    i_in_new = cur_transcription.find(self.last_transcription[i:last_len])

                if i_in_new != -1:
                    new_read_pos = self.last_read_pos + i_in_new - i
                    print(f"==Fixing misalignment :: old:{self.last_read_pos} new:{new_read_pos} {self.last_transcription[i:last_len].encode('utf-8')} {i_in_new}")
                else:
                    if self.last_read_pos > 0:
                        self.last_read_pos -= 1
                    '''
                    _sp = cur_transcription[last_len:].find (" ")
                    _dot = cur_transcription[last_len:].find (".")
                    _comma = cur_transcription[last_len:].find (",")

                    _sp = 1000000 if _sp == -1 else _sp
                    _dot = 1000000 if _dot == -1 else _dot
                    _comma = 1000000 if _comma == -1 else _comma

                    new_read_pos = min (_sp, _dot, _comma) + last_len + 1
                    '''
                    new_read_pos = cur_transcription[last_len:].find (" ") + last_len + 1

                if new_read_pos != -1:
                    self.last_read_pos = new_read_pos
                else:
                    return -1
                print (f"Got misalignment, aligning to {new_read_pos}, test={cur_transcription[new_read_pos:].encode('utf-8')}", flush=True)
                #print (f"last={self.last_transcription.encode('utf-8')}", flush=True)
                #print (f"curr={cur_transcription.encode('utf-8')}", flush=True)

        # find end_pos.
        end_pos = len(cur_transcription)
        if len(cur_transcription)- self.last_read_pos > G_MAX_SUB_CHARS:
            for i in range(self.last_read_pos + G_MAX_SUB_CHARS - 1, -1, -1):
                if cur_transcription[i] in [" ", ".", ","]:
                    break
            if i <= self.last_read_pos:
                print ("Something went wrong, no space character found. Cutting abruptly.", flush=True)
                end_pos = self.last_read_pos + G_MAX_SUB_CHARS
            else:
                end_pos = i+1
        return end_pos

    def get_duration (self, end_pos, durms=0):
        key_start = min(self.pos_pts_map.keys (), key=lambda x:abs(x-self.last_read_pos))
        if durms == G_TIMEOUT_MSECONDS:
            return self.pos_pts_map[key_start],durms
        # below line find the nearest key in list to self.last_read_pos
        # Reference: https://stackoverflow.com/questions/12141150/from-list-of-integers-get-number-closest-to-a-given-value
        key_start = min(self.pos_pts_map.keys (), key=lambda x:abs(x-self.last_read_pos))
        key_end = min(self.pos_pts_map.keys (), key=lambda x:abs(x-end_pos))
        #print (self.pos_pts_map)
        #print (f"==ks={self.last_read_pos}==ke={end_pos}===e={key_end} - s={key_start}========{self.pos_pts_map[key_end] - self.pos_pts_map[key_start]}")
        return self.pos_pts_map[key_start],(self.pos_pts_map[key_end] - self.pos_pts_map[key_start])

    def write (self, cur_transcription, durms=0, is_final=0):
        if len (cur_transcription) > self.last_read_pos:
            if is_final:
                end_pos = self.align_to_next_word (cur_transcription, False)
                if end_pos == -1:
                    return -1
                #end_pos = len(cur_transcription)
            else:
                end_pos = self.align_to_next_word (cur_transcription, durms == G_TIMEOUT_MSECONDS)
                if end_pos == -1:
                    return -1
            tc_in, durms = self.get_duration (end_pos, durms)
            #print (f"tc_in={tc_in}  durms= {durms}")

            '''if (tc_in < self.last_sub_end_pts) and \
              (self.last_sub_end_pts-tc_in > 20000):
                tc_in = self.last_sub_end_pts
                durms = G_MIN_SUB_DURATION_MS'''

            if durms > G_MAX_SUB_DURATION_MS:
                durms = G_MAX_SUB_DURATION_MS
            if durms < G_MIN_SUB_DURATION_MS:
                durms = G_MIN_SUB_DURATION_MS
            try:
                self.srt_writer (cur_transcription[self.last_read_pos:end_pos], tc_in, durms)
            except:
                print(traceback.format_exc(), flush=True)
            self.last_sub_end_pts = tc_in + durms
            self.last_read_pos = end_pos #len (cur_transcription)
            self.last_transcription = cur_transcription[:end_pos]
            #print (f"==== {end_pos} ==== {self.last_transcription[:end_pos]}")
            return 0
        return 0

    def run(self):
        print ("Starting " + self.name, flush=True)
        loop_count = 0
        while not self.exit_flag:
            try:
                result = stream = None
                stream, result = self.q.get(timeout=G_TIMEOUT_SECONDS)
            except:
                #print (f"exception {get_current_time ()}", flush=True)
                if len(self.pos_pts_map) == 0 or not self.last_transcription:
                    continue
                #cur_transcription = result.alternatives[0].transcript
                #cur_timestamp = result.result_end_time.seconds*1000 + result.result_end_time.nanos/1000000
                #self.pos_pts_map[self.last_read_pos] = cur_timestamp
                #self.pos_pts_map[len(cur_transcription)] = cur_timestamp+(G_TIMEOUT_MSECONDS)
                self.write (cur_transcription, G_TIMEOUT_MSECONDS)
                continue

            try:
                cur_transcription = result.alternatives[0].transcript
                x = cur_timestamp = (stream.restart_counter * G_STREAMING_LIMIT) + \
                        result.result_end_time.seconds*1000 + \
                        result.result_end_time.nanos/1000000 - \
                        stream.old_data_sent_ms
                cur_timestamp = stream.get_mapped_audio_pts (cur_timestamp)
                self.pos_pts_map[self.last_transcript_len] = cur_timestamp
                #print (f"----{x} -------- {cur_timestamp}")
                
                if result.is_final:
                    print (f"=FINAL===={cur_transcription.encode('utf-8')}=====", flush=True)
                    while len(cur_transcription) - self.last_read_pos > 1:
                        ret = self.write (cur_transcription.strip(), 0, True)
                        if ret == -1:
                            break
                    self.pos_pts_map.clear ()
                    self.last_transcription = ""
                    self.last_read_pos = 0
                    self.last_transcript_len = 0
                    #self.last_srt_sub.clear ()
                    continue

                #print (cur_transcription)
                curr_len = len (cur_transcription)
                key_last_pos = min(self.pos_pts_map.keys (), key=lambda x:abs(x-self.last_read_pos))
                if (curr_len > self.last_read_pos and \
                    (curr_len-self.last_read_pos > G_WRITE_AFTER_CHARACTERS_RECVD)) or \
                    (cur_timestamp - self.pos_pts_map[key_last_pos] > (G_TIMEOUT_MSECONDS)):
                    self.write (cur_transcription.strip())

                self.last_transcript_len = curr_len
            except:
                print(traceback.format_exc(), flush=True)
        print ("Exiting " + self.name)

def listen_print_loop(q, responses, stream_obj):
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.
    """
    num_chars_printed = 0
    for response in responses:
        if stream_obj.consumed_ms >= G_STREAMING_LIMIT:
            #stream_obj.stream_time = get_current_time ()
            print (f"timeout breaking out of responses loop, consumed_ms={stream_obj.consumed_ms}")
            #break

        if not response.results:
            continue

        # The `results` list is consecutive. For streaming, we only care about
        # the first result being considered, since once it's `is_final`, it
        # moves on to considering the next utterance.
        result = response.results[0]
        #sys.stdout.write(response + '\r')
        #sys.stdout.flush()
        #return
        

        # Display the transcription of the top alternative.
        if result.stability < 0.85 and (not result.is_final):
            continue

        '''with open ("result.json", "a") as fp:
            fp.write (str(result))
            fp.write (f"\n==========={result.is_final}========================================\n")
        '''
        if not result.alternatives:
            continue

        transcript = result.alternatives[0].transcript
        q.put ([stream_obj, result])
        stream_obj.last_sub_pts = result.result_end_time.seconds*1000 + \
                                  result.result_end_time.nanos/1000000 - \
                                  stream_obj.old_data_sent_ms

        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        #
        # If the previous result was longer than this one, we need to print
        # some extra spaces to overwrite the previous result
        overwrite_chars = ' ' * (num_chars_printed - len(transcript))

        if not result.is_final:
            #sys.stdout.write(transcript + overwrite_chars + '\r')
            sys.stdout.flush()

            num_chars_printed = len(transcript)

        else:
            print((transcript+ overwrite_chars).encode('utf-8'))

            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            if re.search(r'\b(exit|quit)\b', transcript, re.I):
                print('Exiting..')
                break

            num_chars_printed = 0

def audio_header_get_pts (data):
    return int.from_bytes(data[4:12], byteorder='little')

def audio_header_get_data_length (data):
    return int.from_bytes(data[12:14], byteorder='little')

class ReadGen(threading.Thread):
    def __init__ (self, inp_file, G_CHUNK_SIZE_BYTES, q):
        threading.Thread.__init__(self)
        self.fname = inp_file
        self.fp = open (self.fname, mode="rb")
        self.chunk = G_CHUNK_SIZE_BYTES 
        self.exit_flag = False
        self.q = q
        self.last_log_time = time.time()
        self.data_read = 0

    def get_sync_byte_position (self, data):
        sync_byte = 'c0ffeeee'
        # /2 as 0xff is one byte but ff are two chars
        return int(data.hex().find (sync_byte)/2)

    def re_align (self,old_data, sync_pos):
        if len(old_data) - sync_pos >= G_AUDIO_HEADER_LEN:
            data_len = audio_header_get_data_length (old_data[sync_pos:])
            old_data_len = len (old_data) - sync_pos - G_AUDIO_HEADER_LEN
            print (f"{data_len} ol={old_data_len} ... ")
            new_data = self.fp.read (data_len-old_data_len)
            final_data = old_data[sync_pos:] + new_data
            self.q.put (final_data)
        
    def run (self):
        while not self.exit_flag:
            #time.sleep(0.01)
            data = self.fp.read (self.chunk+G_AUDIO_HEADER_LEN)
            self.data_read += 32
            #TODO: 32 should be a constant
            now = time.time ()
            if now - self.last_log_time >= 5:
                #TODO: '5' should be made a configuration item
                print (f"Data read in last 5000ms is {self.data_read}ms")
                self.data_read = 0
                self.last_log_time = now
            if data and data[0:4].hex() != 'c0ffeeee':
                print ("Could not get Sync bytes.")
                pos = self.get_sync_byte_position (data)
                if pos == -1:
                    print ("Could not get Sync bytes in the entire packet, dropping it.")
                    continue
                else:
                    print (f"Re-aligning ...{pos}.......{data[pos:pos+5].hex()}....{audio_header_get_pts (data[pos:])}.........")
                    self.re_align (data, pos)
                    continue
            #else:
            #    print ('Got syncbyte')
            self.q.put (data)

class GeneratorClass ():
    def __init__ (self, q, stream):
        self.q = q
        self.exit_flag = False
        self.stream = stream

    def parse_audio_packet (self, data):
        if data and data[0:4].hex() != 'c0ffeeee':
            print (f"Could not get Sync bytes. Aborting...{data[0:4].hex()}")
            os._exit (0)
        #print (f"{data[4:9].hex()} ========")
        pts = audio_header_get_pts (data)
        data_len = audio_header_get_data_length (data)
        running_pts = (self.stream.restart_counter * G_STREAMING_LIMIT) + self.stream.consumed_ms
        #print (f"add map[{running_pts}] = {pts}")
        
        self.stream.audio_pts_map_lock.acquire ()
        self.stream.audio_pts_map[running_pts] = pts
        self.stream.audio_pts_map_lock.release ()
        #print (f"pts:{pts} len:{data_len} {len(data[G_AUDIO_HEADER_LEN:data_len+G_AUDIO_HEADER_LEN])}========")
        #print(data[10:data[9]])
        return data[G_AUDIO_HEADER_LEN:data_len+G_AUDIO_HEADER_LEN]

    def get_bytes (self):
        data = self.stream.get_data_from_pts ()
        if data:
            yield data
        while not self.exit_flag and self.stream.consumed_ms < G_STREAMING_LIMIT:

            try:
                data = self.parse_audio_packet (self.q.get ())
                self.stream.push_to_sent_q (data)
                self.stream.consumed_ms += G_CHUNK_MS
                yield data
            except:
                print(traceback.format_exc(), flush=True)
                os._exit(1)


        print (f"Exiting generator, bytes put = {self.stream.consumed_ms}", flush=True)

def main(audio_pipe_fname, srt_pipe_srt_fname, phrases_fname):
    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    language_code = 'en-US'  # a BCP-47 language tag

    q_obj = queue.Queue ()
    audio_q = queue.Queue(maxsize=G_MAX_AUDIO_BUFFER)
    thread_obj = myThread (1, "audio_to_srt_1", q_obj, srt_pipe_srt_fname)
    thread_obj.start ()
    
    phrases = ["BEIN SPORTS", "BEIN SPORTS EXTRA"]
    if (len(phrases_fname) > 0):
        try:
            with open (phrases_fname, "r", encoding='utf-8') as fp:
                for line in fp:
                    if line:
                        ascii_line = line.strip().encode ('ascii', 'ignore').decode('ascii')
                        phrases.append (ascii_line)
                        eprint("added phrase:", ascii_line)
        except:
            print(traceback.format_exc(), flush=True)
 
    speech_context = speech.types.SpeechContext(phrases=phrases[:5000])
    try:
        client = speech.SpeechClient()
        config = types.RecognitionConfig(
            encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=G_AUD_SAMPLING_RATE,
            enable_word_time_offsets=False,
            model='video',
            profanity_filter=True,
            enable_automatic_punctuation=True,
            speech_contexts=[speech_context],
            language_code=language_code)
        streaming_config = types.StreamingRecognitionConfig(
            config=config,
            interim_results=True)
    except google.auth.exceptions.DefaultCredentialsError:
        print ("Export authorization json in environment", flush=True)
        thread_obj.exit_flag = True
        thread_obj.join ()
        sys.exit(1)
    except:
        print(traceback.format_exc(), flush=True)
        sys.exit(1)

    stream_obj = StreamDataStructure ()

    print (f"Number of phrases as context = {len(phrases)}")

    reader = ReadGen (audio_pipe_fname, G_CHUNK_SIZE_BYTES, audio_q)
    reader.start ()

    while True:
        try:
            generator_obj = GeneratorClass (audio_q, stream_obj)
            audio_generator = generator_obj.get_bytes()
            for data in audio_generator:
                break
            requests = (types.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator)

            responses = client.streaming_recognize(streaming_config, requests)

            # Now, put the transcription responses to use.
            listen_print_loop(q_obj, responses, stream_obj)
            stream_obj.restart_counter += 1
            stream_obj.last_iter_consumed_ms += stream_obj.consumed_ms
            stream_obj.consumed_ms = 0
            print (f"===============RETRY AFTER 5MIN======last_sent={stream_obj.last_sub_pts}", flush=True)
            if len(stream_obj.audio_pts_map.keys ()) > 0:
                lk = list(stream_obj.audio_pts_map.keys ())[-1]
                print (f"===audio_pts_map[{lk}] = {stream_obj.audio_pts_map[lk]}===========", flush=True)

        except google.api_core.exceptions.ServiceUnavailable:
            print ("===============ServiceUnavailable exception.===RETRY===================", flush=True)
            #generator_obj.exit_flag = True
            time.sleep (5)
        except:
            print(traceback.format_exc(), flush=True)
            thread_obj.exit_flag = True 
            #generator_obj.exit_flag = True
            thread_obj.join ()
            print ("Exited writer")
            break

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
    sys.stderr.flush()

def validate_configuration(config):

    if (not G_FILES_SECTION_NAME in config):
        eprint("FILES section not present in configuration file")
        sys.exit(1)

    if (not G_INPUT_AUDIO_PATH_CFG_NAME in config[G_FILES_SECTION_NAME]):
        eprint(G_INPUT_AUDIO_PATH_CFG_NAME, "not present in configuration")
        sys.exit(1)

    if (not G_OUTPUT_SRT_PATH_CFG_NAME in config[G_FILES_SECTION_NAME]):
        eprint(G_OUTPUT_SRT_PATH_CFG_NAME, "not present in configuration")
        sys.exit(1)

    if (not G_GCP_AUTH_PATH_CFG_NAME in config[G_FILES_SECTION_NAME]):
        eprint(G_GCP_AUTH_PATH_CFG_NAME, "not present in configuration")
        sys.exit(1)

def dump_configuration(config):
    #https://stackoverflow.com/questions/23662280/how-to-log-the-contents-of-a-configparser
    eprint({section: dict(config[section]) for section in config.sections()})

def apply_configuration(config):

    global G_TIMEOUT_SECONDS
    global G_TIMEOUT_MSECONDS
    global G_REPEAT_SUB_THREASHOLD_MS
    global G_WRITE_AFTER_CHARACTERS_RECVD
    global G_MAX_SUB_CHARS
    global G_STREAMING_LIMIT
    global G_MIN_SUB_DURATION_MS
    global G_MAX_SUB_DURATION_MS

    gcp_auth_path = config[G_FILES_SECTION_NAME][G_GCP_AUTH_PATH_CFG_NAME]

    if (not os.path.isfile (gcp_auth_path)):
        eprint(gcp_auth_path, "not found")
        sys.exit(1)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = gcp_auth_path

    if (not G_PHRASES_PATH_CFG_NAME in config[G_FILES_SECTION_NAME]):
        config.set(G_FILES_SECTION_NAME, G_PHRASES_PATH_CFG_NAME, "")

    if (G_TRANSLATION_SECTION_NAME in config):

        if (G_TIMEOUT_SECONDS_CFG_NAME in config[G_TRANSLATION_SECTION_NAME]):
            G_TIMEOUT_SECONDS = config[G_TRANSLATION_SECTION_NAME].getint(G_TIMEOUT_SECONDS_CFG_NAME)
            G_TIMEOUT_MSECONDS = G_TIMEOUT_SECONDS*1000

        if (G_REPEAT_SUB_THREASHOLD_MS_CFG_NAME in config[G_TRANSLATION_SECTION_NAME]):
            G_REPEAT_SUB_THREASHOLD_MS = config[G_TRANSLATION_SECTION_NAME].getint(G_REPEAT_SUB_THREASHOLD_MS_CFG_NAME)

        if (G_WRITE_AFTER_CHARACTERS_RECVD_CFG_NAME in config[G_TRANSLATION_SECTION_NAME]):
            G_WRITE_AFTER_CHARACTERS_RECVD = config[G_TRANSLATION_SECTION_NAME].getint(G_WRITE_AFTER_CHARACTERS_RECVD_CFG_NAME)

        if (G_MAX_SUB_CHARS_CFG_NAME in config[G_TRANSLATION_SECTION_NAME]):
            G_MAX_SUB_CHARS = config[G_TRANSLATION_SECTION_NAME].getint(G_MAX_SUB_CHARS_CFG_NAME)

        if (G_STREAMING_LIMIT_CFG_NAME in config[G_TRANSLATION_SECTION_NAME]):
            G_STREAMING_LIMIT = config[G_TRANSLATION_SECTION_NAME].getint(G_STREAMING_LIMIT_CFG_NAME)

        if (G_MIN_SUB_DURATION_MS_CFG_NAME in config[G_TRANSLATION_SECTION_NAME]):
            G_MIN_SUB_DURATION_MS = config[G_TRANSLATION_SECTION_NAME].getint(G_MIN_SUB_DURATION_MS_CFG_NAME)

        if (G_MAX_SUB_DURATION_MS_CFG_NAME in config[G_TRANSLATION_SECTION_NAME]):
            G_MAX_SUB_DURATION_MS = config[G_TRANSLATION_SECTION_NAME].getint(G_MAX_SUB_DURATION_MS_CFG_NAME)

def dump_parameters():

    eprint("#--- Fixed Audio recording parameters ---")
    eprint("G_BYTE_PER_SAMPLE = ", G_BYTE_PER_SAMPLE)
    eprint("G_AUD_SAMPLING_RATE = ", G_AUD_SAMPLING_RATE)
    eprint("G_CHUNK_MS = ", G_CHUNK_MS)
    eprint("G_CHUNK_SIZE_BYTES = ", G_CHUNK_SIZE_BYTES)

    eprint("#--- Fixed Input packet parameters ---")
    eprint("G_AUDIO_HEADER_LEN = ", G_AUDIO_HEADER_LEN)

    eprint("#--- Translation process parameters ---")
    eprint("G_TIMEOUT_SECONDS = ", G_TIMEOUT_SECONDS)
    eprint("G_TIMEOUT_MSECONDS = ", G_TIMEOUT_MSECONDS)
    eprint("G_REPEAT_SUB_THREASHOLD_MS = ", G_REPEAT_SUB_THREASHOLD_MS)
    eprint("G_WRITE_AFTER_CHARACTERS_RECVD = ", G_WRITE_AFTER_CHARACTERS_RECVD)
    eprint("G_MAX_SUB_CHARS = ", G_MAX_SUB_CHARS)
    eprint("G_STREAMING_LIMIT = ", G_STREAMING_LIMIT)
    eprint("G_MIN_SUB_DURATION_MS = ", G_MIN_SUB_DURATION_MS)
    eprint("G_MAX_SUB_DURATION_MS = ", G_MAX_SUB_DURATION_MS)
    eprint("G_MAX_AUDIO_BUFFER = ", G_MAX_AUDIO_BUFFER)

def usage():
    eprint("TODO: usage")

if __name__ == '__main__':

    opt_cfg_path = ""
    opt_verbose = False
    opt_no_run = False

    try:
        opts, args = getopt.getopt(sys.argv[1:], 
                                   "hc:vn", 
                                   ["help",
                                    "conf=",
                                    "verbose",
                                    "norun"
                                   ]
                                   )
    except getopt.GetoptError as err:
        # print help information and exit:
        print(err) # will print something like "option -a not recognized"
        sys.exit(1)

    for o, v in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-c", "--conf"):
            opt_cfg_path = v
        elif o in ("-v", "--verbose"):
            opt_verbose = True
        elif o in ("-n", "--norun"):
            opt_no_run = True
        else:
            assert False, "unhandled option"

    if (len(opt_cfg_path) == 0):
        eprint("-c option is not specified")
        sys.exit(1)
    elif (not os.path.isfile (opt_cfg_path)):
        eprint("configuration file", opt_cfg_path, "not found")
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(opt_cfg_path)
    if (opt_verbose):
        dump_configuration(config)
    validate_configuration(config)
    apply_configuration(config)
    if (opt_verbose):
        dump_parameters()

    if (opt_no_run):
        sys.exit(0)

    while True:
        try:
            main(config[G_FILES_SECTION_NAME].get(G_INPUT_AUDIO_PATH_CFG_NAME),
                 config[G_FILES_SECTION_NAME].get(G_OUTPUT_SRT_PATH_CFG_NAME),
                 config[G_FILES_SECTION_NAME].get(G_PHRASES_PATH_CFG_NAME))
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            eprint(traceback.format_exc())
            sys.exit(1)

