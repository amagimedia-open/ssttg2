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
from datetime import datetime
import argparse
from collections import OrderedDict
import configparser

import google
from google.cloud import speech
#from google.cloud.speech import enums
#from google.cloud.speech import types

import stt_commons as comn
import amg_logger  as logr
import stt_globals as glbl
import stt_cmdargs as args
import stt_default_config
from   response_to_srt    import ResponseToSRT
from   stt_data_structure import StreamDataStructure
from   stt_google_response_interface import *

#from stt_globals import *

#+-----------+
#| FUNCTIONS |
#+-----------+

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

    global main_logger

    num_chars_printed = 0
    for response in responses:
        if stream_obj.consumed_ms >= G_STREAMING_LIMIT:
            #stream_obj.stream_time = get_current_time ()
            main_logger.info(f"timeout breaking out of responses loop, consumed_ms={stream_obj.consumed_ms}")
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

        if not result.alternatives:
            continue
        
        time_now = time.time ()

        transcript = result.alternatives[0].transcript
        amg_result = ResponeInterface ()
        google_response_to_amg (result, amg_result)
        q.put ([stream_obj, amg_result, time_now])
        stream_obj.last_sub_pts = result.result_end_time.seconds*1000 + \
                                  result.result_end_time.microseconds/1000 - \
                                  stream_obj.old_data_sent_ms

        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        #
        # If the previous result was longer than this one, we need to print
        # some extra spaces to overwrite the previous result
        overwrite_chars = ' ' * (num_chars_printed - len(transcript))

        if not result.is_final:
            #sys.stdout.write(transcript + overwrite_chars + '\r')
            #sys.stdout.flush()

            num_chars_printed = len(transcript)
        else:
            pass
            #eprint((transcript+ overwrite_chars).encode('utf-8'))

            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            #if re.search(r'\b(exit|quit)\b', transcript, re.I):
            #    eprint('Exiting..')
            #    break

            num_chars_printed = 0

def audio_header_get_pts (data):
    return int.from_bytes(data[4:12], byteorder='little')

def audio_header_get_data_length (data):
    return int.from_bytes(data[12:14], byteorder='little')

class ReadGen(threading.Thread):
    def __init__ (self, inp_file, G_CHUNK_SIZE_BYTES, q, exit_on_zero_size):
        threading.Thread.__init__(self)
        self.fname = inp_file
        self.fp = open (self.fname, mode="rb")
        self.chunk = G_CHUNK_SIZE_BYTES 
        self.exit_flag = False
        self.q = q
        self.last_log_time = time.time()
        self.data_read = 0
        self.logger = logr.amagi_logger (
                        "com.amagi.stt.readgen",
                        logr.LOG_INFO, 
                        log_stream=G_LOGGER_STREAM)

    def get_sync_byte_position (self, data):
        sync_byte = 'c0ffeeee'
        # /2 as 0xff is one byte but ff are two chars
        return int(data.hex().find (sync_byte)/2)

    def re_align (self,old_data, sync_pos):
        if len(old_data) - sync_pos >= G_AUDIO_HEADER_LEN:
            data_len = audio_header_get_data_length (old_data[sync_pos:])
            old_data_len = len (old_data) - sync_pos - G_AUDIO_HEADER_LEN
            self.logger.info (f"{data_len} ol={old_data_len}")
            new_data = self.fp.read (data_len-old_data_len)
            final_data = old_data[sync_pos:] + new_data
            self.q.put (final_data)
        
    def run (self):
        while not self.exit_flag:
            #time.sleep(0.01)
            data = self.fp.read (self.chunk+G_AUDIO_HEADER_LEN)
            self.data_read += 32
            now = time.time ()
            if now - self.last_log_time >= 5:
                self.logger.info (f"Data read in last 5000ms is {self.data_read}ms")
                self.data_read = 0
                self.last_log_time = now
            if data and data[0:4].hex() != 'c0ffeeee':
                self.logger.warn ("Could not get Sync bytes.")
                pos = self.get_sync_byte_position (data)
                if pos == -1:
                    self.logger.info ("Could not get Sync bytes in the entire packet, dropping it.")
                    continue
                else:
                    self.logger.info (f"Re-aligning ...{pos}...{data[pos:pos+5].hex()}...{audio_header_get_pts (data[pos:])}..")
                    self.re_align (data, pos)
                    continue
            #else:
            #    print ('Got syncbyte')
            if (audio_header_get_data_length (data)) == 0:
                main_logger.warn ("Received audio packet with length=0, Exiting...")
                glbl.G_EXIT_FLAG = True
                break
            self.q.put (data)

class GeneratorClass ():
    def __init__ (self, q, stream):
        self.q = q
        self.exit_flag = False
        self.stream = stream
        self.logger = logr.amagi_logger (
                        "com.amagi.stt.GeneratorClass", 
                        logr.LOG_INFO, 
                        log_stream=glbl.G_LOGGER_STREAM)
        self.time0_ms = 0

    def parse_audio_packet (self, data):
        if data and data[0:4].hex() != 'c0ffeeee':
            self.logger.error(f"Could not get Sync bytes. Aborting...{data[0:4].hex()}")
            os._exit (0)
        #print (f"{data[4:9].hex()} ========")
        pts = audio_header_get_pts (data)
        data_len = audio_header_get_data_length (data)
        running_pts = (self.stream.restart_counter * G_STREAMING_LIMIT) + self.stream.consumed_ms
        #print (f"add map[{running_pts}] = {pts}")
        if (pts > 0):
            curr_time_ms = comn.now_2_epochms()
            if (self.time0_ms == 0):
                self.time0_ms = curr_time_ms
            rel_time_ms = curr_time_ms - self.time0_ms
            self.logger.info(f"Received-data: reltime={rel_time_ms}, pts={pts}, len={data_len}")
        
        self.stream.audio_pts_map_lock.acquire ()
        self.stream.audio_pts_map[running_pts] = pts
        self.stream.audio_pts_map_lock.release ()
        #print (f"pts:{pts} len:{data_len} {len(data[G_AUDIO_HEADER_LEN:data_len+G_AUDIO_HEADER_LEN])}========")
        #print(data[10:data[9]])
        return data[G_AUDIO_HEADER_LEN:data_len+G_AUDIO_HEADER_LEN]

    def get_bytes (self):
        global main_logger

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
                main_logger.error(traceback.format_exc())
                os._exit(1)


        self.logger.info (f"Exiting generator, bytes put = {self.stream.consumed_ms}")

def main():

    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    global G_EXIT_FLAG
    global main_logger

    language_code = 'en-US'  # a BCP-47 language tag

    q_obj = queue.Queue ()
    audio_q = queue.Queue(maxsize=G_MAX_AUDIO_BUFFER)

    response_to_srt_obj = ResponseToSRT (q_obj)
    response_to_srt_obj.start ()
    
    phrases = []
    if (len(glbl.G_PHRASES_PATH) != 0):
        try:
            with open (glbl.G_PHRASES_PATH, "r", encoding='utf-8') as fp:
                for line in fp:
                    if line:
                        phrases.append (line.strip().encode ('ascii', 'ignore').decode('ascii'))
        except FileNotFoundError:
            main_logger.info(f"Phrases file {glbl.G_PHRASES_PATH} is not present.")
        except:
            main_logger.error(traceback.format_exc())
    else:
        main_logger.info(f"Phrases file {glbl.G_PHRASES_PATH} is null.")
 
    speech_context = speech.SpeechContext(phrases=phrases[:5000])
    try:
        client = speech.SpeechClient()
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=G_AUD_SAMPLING_RATE,
            enable_word_time_offsets=False,
            model='video',
            profanity_filter=True,
            enable_automatic_punctuation=True,
            speech_contexts=[speech_context],
            language_code=language_code)
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True)
    except google.auth.exceptions.DefaultCredentialsError:
        main_logger.error("Export authorization json in environment")
        response_to_srt_obj.exit_flag = True
        response_to_srt_obj.join ()
        sys.exit(1)
    except:
        main_logger.error(traceback.format_exc())
        sys.exit(1)

    stream_obj = StreamDataStructure ()
    main_logger.info(f"Number of phrases as context = {len(phrases)}")

    reader = ReadGen (glbl.G_INPUT_AUDIO_PATH, 
                      glbl.G_CHUNK_SIZE_BYTES, 
                      audio_q, \
                      exit_on_zero_size=glbl.G_IFLAGS_EXIT_ON_ZERO_SIZE)
    reader.start ()

    while not G_EXIT_FLAG:
        try:
            generator_obj = GeneratorClass (audio_q, stream_obj)
            audio_generator = generator_obj.get_bytes()
            for data in audio_generator:
                break
            requests = (speech.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator)

            responses = client.streaming_recognize(streaming_config, requests)

            # Now, put the transcription responses to use.
            listen_print_loop(q_obj, responses, stream_obj)
            stream_obj.restart_counter += 1
            stream_obj.last_iter_consumed_ms += stream_obj.consumed_ms
            stream_obj.consumed_ms = 0
            main_logger.info("===============RETRY AFTER 5MIN======last_sent={stream_obj.last_sub_pts}")
            if len(stream_obj.audio_pts_map.keys ()) > 0:
                lk = list(stream_obj.audio_pts_map.keys ())[-1]
                main_logger.info(f"===audio_pts_map[{lk}] = {stream_obj.audio_pts_map[lk]}===========")

        except google.api_core.exceptions.ServiceUnavailable:
            main_logger.info("===============ServiceUnavailable exception.===RETRY===================")
            time.sleep (5)
        except:
            main_logger.error(traceback.format_exc())
            response_to_srt_obj.exit_flag = True 
            generator_obj.exit_flag = True
            response_to_srt_obj.join ()
            main_logger.info ("## Exited writer")
            G_EXIT_FLAG = True
            break

def usage():
    global main_logger

    main_logger.info("TODO: usage")

if __name__ == '__main__':

    global G_EXIT_FLAG
    global main_logger

    (dump_def_config, cp) = args.gen_config_from_cmdargs (sys.argv[1:])
    if (dump_def_config):
        comn.eprint(stt_default_config.stt_default_config_str)
        os._exit(0)

    glbl.config_2_globals(cp)

    if (glbl.G_VERBOSE):
        glbl.dump_globals()

    if (glbl.G_NO_RUN):
        sys.exit(0)

    # see stt_globals.py
    main_logger = logr.amagi_logger (
                  "com.amagi.stt.main", 
                  logr.LOG_INFO, 
                  log_stream=glbl.G_LOGGER_STREAM)

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = glbl.G_GCP_AUTH_PATH
    
    while not G_EXIT_FLAG:
        try:
            main()
            main_logger.info("main() over")
        except KeyboardInterrupt:
            G_EXIT_FLAG = True
            sys.exit(0)
        except:
            main_logger.error(traceback.format_exc())
            sys.exit(1)

    main_logger.info ("### Exited Main")
    os._exit(0)

