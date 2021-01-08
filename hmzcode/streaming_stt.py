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
import stt_default_config as defconf
from   stt_srt_writer       import SRTWriter
from   stt_pcm_stream_state import PCMStreamState
from   stt_google_response_interface import *

#from stt_globals import *

#+-----------+
#| FUNCTIONS |
#+-----------+

def queue_transcription_responses(responses, pcm_stream_state, q):
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
        if pcm_stream_state.consumed_ms >= glbl.G_STREAMING_LIMIT:
            #pcm_stream_state.stream_time = get_current_time ()
            main_logger.info(f"timeout breaking out of responses loop,"
                              "consumed_ms={pcm_stream_state.consumed_ms}")
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
        if result.stability < glbl.G_MIN_TRANSCRIPTION_STABILITY and \
           (not result.is_final):
            continue

        if not result.alternatives:
            continue
        
        time_now = time.time ()

        transcript = result.alternatives[0].transcript
        amg_result = ResponeInterface ()
        google_response_to_amg (result, amg_result)
        q.put ([pcm_stream_state, amg_result, time_now])

        result_end_time_ms = result.result_end_time.seconds*1000 + \
                             result.result_end_time.microseconds/1000
        pcm_stream_state.update_last_sub_pts (result_end_time_ms)

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

class PacketizedPCMReader(threading.Thread):
    def __init__ (self, q):
        threading.Thread.__init__(self)
        self.fname = glbl.G_INPUT_AUDIO_PATH
        self.fp = open (self.fname, mode="rb")
        self.chunk = glbl.G_CHUNK_SIZE_BYTES 
        self.exit_flag = False
        self.q = q
        self.last_log_time = time.time()
        self.data_read = 0
        self.logger = logr.amagi_logger (
                        "com.amagi.stt.packpcmreader",
                        logr.LOG_INFO, 
                        log_stream=glbl.G_LOGGER_STREAM)

    def get_sync_byte_position (self, data):
        sync_byte = 'c0ffeeee'
        # /2 as 0xff is one byte but ff are two chars
        return int(data.hex().find (sync_byte)/2)

    def re_align (self,old_data, sync_pos):
        if len(old_data) - sync_pos >= glbl.G_AUDIO_HEADER_LEN:
            data_len = audio_header_get_data_length (old_data[sync_pos:])
            old_data_len = len (old_data) - sync_pos - glbl.G_AUDIO_HEADER_LEN
            self.logger.info (f"{data_len} ol={old_data_len}")
            new_data = self.fp.read (data_len-old_data_len)
            final_data = old_data[sync_pos:] + new_data
            self.q.put (final_data)
        
    def run (self):
        while not self.exit_flag:
            #time.sleep(0.01)
            data = self.fp.read (self.chunk+glbl.G_AUDIO_HEADER_LEN)
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

class PCMPacketGenerator ():
    def __init__ (self, q, stream):
        self.q = q
        self.exit_flag = False
        self.stream = stream
        self.logger = logr.amagi_logger (
                        "com.amagi.stt.PCMPacketGenerator", 
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
        running_pts = (self.stream.restart_counter * glbl.G_STREAMING_LIMIT) + self.stream.consumed_ms
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
        #print (f"pts:{pts} len:{data_len} {len(data[glbl.G_AUDIO_HEADER_LEN:data_len+G_AUDIO_HEADER_LEN])}========")
        #print(data[10:data[9]])
        return data[glbl.G_AUDIO_HEADER_LEN : data_len+glbl.G_AUDIO_HEADER_LEN]

    def get_bytes (self):
        global main_logger

        data = self.stream.get_data_from_pts ()
        if data:
            yield data

        while not self.exit_flag and self.stream.consumed_ms < glbl.G_STREAMING_LIMIT:

            try:
                data = self.parse_audio_packet (self.q.get ())
                self.stream.push_to_sent_q (data)
                self.stream.incr_consumed_ms(glbl.G_CHUNK_MS)
                yield data
            except:
                main_logger.error(traceback.format_exc())
                os._exit(1)


        self.logger.info (f"Exiting generator, bytes put = {self.stream.consumed_ms}")


def get_phrases_list ():
    phrases = []

    if (len(glbl.G_PHRASES_PATH) != 0):
        try:
            with open (glbl.G_PHRASES_PATH, "r", encoding=glbl.G_PHRASES_ENCODING) as fp:
                for line in fp:
                    if line:
                        phrases.append (line.strip().encode ('ascii', 'ignore').decode('ascii'))
        except FileNotFoundError:
            main_logger.info(f"Phrases file {glbl.G_PHRASES_PATH} is not present.")
        except:
            main_logger.error(traceback.format_exc())
    else:
        main_logger.info(f"Phrases file {glbl.G_PHRASES_PATH} is null.")

    return phrases


def create_sstt_client_and_config():
    """
        returns a tuple (client, config)
    """

    phrases = get_phrases_list ()
    main_logger.info(f"Number of phrases as context = {len(phrases)}")
    speech_context = speech.SpeechContext(phrases=phrases[:glbl.G_MAX_PHRASES])

    try:
        client = speech.SpeechClient()

        config = speech.RecognitionConfig(
                    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                    sample_rate_hertz=glbl.G_AUD_SAMPLING_RATE,
                    enable_word_time_offsets=False,
                    model='video',
                    profanity_filter=True,
                    enable_automatic_punctuation=True,
                    speech_contexts=[speech_context],
                    language_code=glbl.G_LANGUAGE_CODE)

        streaming_config = speech.StreamingRecognitionConfig(
                            config=config,
                            interim_results=True)

        return (client, streaming_config)

    except google.auth.exceptions.DefaultCredentialsError:
        main_logger.error("Export authorization json in environment")
        srt_gen.exit_flag = True
        srt_gen.join ()
        sys.exit(1)
    except:
        main_logger.error(traceback.format_exc())
        sys.exit(1)


def main():

    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    global main_logger

    #+---------------------------------------------------------------------+
    #|                                      (thread) PacketizedPCMReader   |
    #|                                                       V             |
    #|                                                   [ pcm_q ]         |
    #|                                                       V             |
    #|                                   requests  ( PCMPacketGenerator )  |
    #|                                      V                .             |
    #|                             streaming_recognize       .             |
    #|                                      V                .             |
    #| queue_transcription_responses ( responses )           .             |
    #|             V              .   <generator>            .             |
    #|             V              +.......................+  .             |
    #| [ transcription_response_q ]                       .  .             |
    #|             V                                      .  .             |
    #|         SRTWriter (thread)                       PCMStreamState     |
    #|                                                                     |
    #+---------------------------------------------------------------------+

    pcm_stream_state = PCMStreamState()

    (streaming_client, streaming_config) = create_sstt_client_and_config()

    transcription_response_q = queue.Queue ()
    srt_gen = SRTWriter (transcription_response_q)
    srt_gen.start ()
    
    pcm_q = queue.Queue (maxsize=glbl.G_MAX_AUDIO_BUFFER)
    reader  = PacketizedPCMReader (pcm_q)
    reader.start ()

    while not glbl.G_EXIT_FLAG:
        try:
            # creating a generator using data supplied by PacketizedPCMReader
            generator_obj = PCMPacketGenerator (pcm_q, pcm_stream_state)
            audio_generator = generator_obj.get_bytes()

            for data in audio_generator:    #blocks until there is data
                break                       #in the audio_generator 

            # the transcription request stream (via a generator)
            requests = (speech.StreamingRecognizeRequest(audio_content=content)
                        for content in audio_generator)

            # the transcription response stream (via a generator)
            responses = streaming_client.streaming_recognize (
                            streaming_config, requests)

            # forwarding responses to a 'q' that is read/handled by SRTWriter
            queue_transcription_responses (
                    responses, 
                    pcm_stream_state, 
                    transcription_response_q)

            # control comes here when there are no more responses
            # this can happen if
            #   (a) there is no more input (or)
            #   (b) streaming_recognize cannot process more than this duration
            #       (in which case we need to set the pcm_stream_state right
            #        and begin all over again)

            pcm_stream_state.on_iteration_complete()

            main_logger.info("=====RETRY AFTER 5MIN====="
                             "last_sent={pcm_stream_state.last_sub_pts}")

            lk = pcm_stream_state.get_last_key()
            if (lk != None):
                main_logger.info(
                    f"=====audio_pts_map[{lk}] = "
                     "{pcm_stream_state.audio_pts_map[lk]}======")

        except google.api_core.exceptions.ServiceUnavailable:

            main_logger.info("=====ServiceUnavailable exception.===RETRY=====")
            time.sleep (glbl.G_RETRY_DURATION_SEC_ON_SERVICE_UNAVAILABLE)

        except:

            main_logger.error(traceback.format_exc())
            srt_gen.exit_flag = True 
            generator_obj.exit_flag = True
            srt_gen.join ()
            main_logger.info ("## Exited writer")
            glbl.G_EXIT_FLAG = True
            break

if __name__ == '__main__':

    global main_logger

    (dump_def_config, cp) = args.gen_config_from_cmdargs (sys.argv[1:])
    if (dump_def_config):
        comn.eprint(defconf.stt_default_config_str)
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
    
    while not glbl.G_EXIT_FLAG:
        try:
            main()
            main_logger.info("main() over")
        except KeyboardInterrupt:
            glbl.G_EXIT_FLAG = True
            sys.exit(0)
        except:
            main_logger.error(traceback.format_exc())
            sys.exit(1)

    main_logger.info ("### Exited Main")
    os._exit(0)

