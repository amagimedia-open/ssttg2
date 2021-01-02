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

from response_to_srt import ResponseToSRT
from stt_data_structure import StreamDataStructure
from stt_globals import *
from stt_google_response_interface import *
import stt_globals
import amg_logger

#+-----------------------------+
#| INI FILE SECTIONS AND NAMES |
#+-----------------------------+

#names under the section FILES in the .ini file

G_FILES_SECTION_NAME="FILES"
G_GCP_AUTH_PATH_CFG_NAME="gcp_auth_path"
G_PHRASES_PATH_CFG_NAME="phrases_path"
G_ENABLE_DEBUG_RESPONSE_DUMP="enable_debug_gcp_response"
G_DEBUG_RESPONSE_DUMP_PATH="debug_gcp_response_path"

#names under the section TRANSLATION in the .ini file

G_TRANSLATION_SECTION_NAME="TRANSLATION"
G_MIN_WORD_DRAIN_DELAY_NAME = "min_word_drain_delay_sec"
G_MAX_INTER_WORD_DURATION_NAME = "max_inter_word_duration_ms"
G_MAX_SUBTITLE_LINE_DURATION_NAME = "max_subtitle_line_duration_ms"
G_MAX_CHARS_IN_SUB_ROW_NAME = "max_chars_in_sub_row"
G_MAX_WORDS_TO_SEARCH_NAME="max_words_to_search"

G_IFLAGS_SECTION_NAME = "IFLAGS"
G_IFLAGS_EXIT_ON_ZERO_SIZE_NAME = "exit_on_zero_size"
G_IFLAGS_LAST_LOG_TIME_QUANTA_MS_NAME = "last_log_time_quanta_ms"

G_OFLAGS_SECTION_NAME = "OFLAGS"
G_OFLAGS_APPEND_MODE_NAME = "append_mode"
G_OFLAGS_APPEND_NULL_CHAR_NAME = "append_null_char"

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
    num_chars_printed = 0
    for response in responses:
        if stream_obj.consumed_ms >= G_STREAMING_LIMIT:
            #stream_obj.stream_time = get_current_time ()
            eprint (f"timeout breaking out of responses loop, consumed_ms={stream_obj.consumed_ms}")
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
        self.logger = amg_logger.amagi_logger ("com.amagi.stt.readgen", amg_logger.LOG_INFO, log_stream=stt_globals.G_LOGGER_STREAM)

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
                self.logger.warn ("Received audio packet with length=0, Exiting...")
                stt_globals.G_EXIT_FLAG = True
                break
            self.q.put (data)

class GeneratorClass ():
    def __init__ (self, q, stream):
        self.q = q
        self.exit_flag = False
        self.stream = stream
        self.logger = amg_logger.amagi_logger ("com.amagi.stt.GeneratorClass", amg_logger.LOG_INFO, log_stream=stt_globals.G_LOGGER_STREAM)

    def parse_audio_packet (self, data):
        if data and data[0:4].hex() != 'c0ffeeee':
            self.logger.error(f"Could not get Sync bytes. Aborting...{data[0:4].hex()}")
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
                eprint(traceback.format_exc(), flush=True)
                os._exit(1)


        self.logger.info (f"Exiting generator, bytes put = {self.stream.consumed_ms}")

def main(audio_pipe_fname, srt_pipe_srt_fname, phrases_fname, dump_gcp_response=""):
    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    global G_EXIT_FLAG
    language_code = 'en-US'  # a BCP-47 language tag

    q_obj = queue.Queue ()
    audio_q = queue.Queue(maxsize=G_MAX_AUDIO_BUFFER)

    if dump_gcp_response:
        dump_gcp_response = dump_gcp_response + "." + \
                datetime.now().strftime("%Y%m%d-%H:%M:%S")

    response_to_srt_obj = ResponseToSRT (1, "audio_to_srt_1", q_obj, \
            srt_pipe_srt_fname, G_OFLAGS_APPEND_MODE, G_OFLAGS_APPEND_NULL_CHAR, \
            dump_gcp_response)
    response_to_srt_obj.start ()
    
    #phrases = ["BEIN SPORTS", "BEIN SPORTS EXTRA"]
    phrases = []
    try:
        with open (phrases_fname, "r", encoding='utf-8') as fp:
            for line in fp:
                if line:
                    phrases.append (line.strip().encode ('ascii', 'ignore').decode('ascii'))
    except FileNotFoundError:
        eprint (f"Phrases file {phrases_fname} is not present.")
    except:
        eprint(traceback.format_exc(), flush=True)
 
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
        eprint ("Export authorization json in environment", flush=True)
        response_to_srt_obj.exit_flag = True
        response_to_srt_obj.join ()
        sys.exit(1)
    except:
        eprint(traceback.format_exc(), flush=True)
        sys.exit(1)

    stream_obj = StreamDataStructure ()

    eprint (f"Number of phrases as context = {len(phrases)}")

    reader = ReadGen (audio_pipe_fname, G_CHUNK_SIZE_BYTES, audio_q, \
            exit_on_zero_size=G_IFLAGS_EXIT_ON_ZERO_SIZE)
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
            eprint (f"===============RETRY AFTER 5MIN======last_sent={stream_obj.last_sub_pts}", flush=True)
            if len(stream_obj.audio_pts_map.keys ()) > 0:
                lk = list(stream_obj.audio_pts_map.keys ())[-1]
                eprint (f"===audio_pts_map[{lk}] = {stream_obj.audio_pts_map[lk]}===========", flush=True)

        except google.api_core.exceptions.ServiceUnavailable:
            eprint ("===============ServiceUnavailable exception.===RETRY===================", flush=True)
            #generator_obj.exit_flag = True
            time.sleep (5)
        except:
            eprint(traceback.format_exc(), flush=True)
            response_to_srt_obj.exit_flag = True 
            generator_obj.exit_flag = True
            response_to_srt_obj.join ()
            eprint ("## Exited writer")
            G_EXIT_FLAG = True
            break

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
    sys.stderr.flush()

def validate_configuration(config):

    if (not G_FILES_SECTION_NAME in config):
        eprint("FILES section not present in configuration file")
        sys.exit(1)

    if (not G_PHRASES_PATH_CFG_NAME in config[G_FILES_SECTION_NAME]):
        eprint(G_PHRASES_PATH_CFG_NAME, "not present in configuration")
        sys.exit(1)

def dump_configuration(config):
    #https://stackoverflow.com/questions/23662280/how-to-log-the-contents-of-a-configparser
    eprint({section: dict(config[section]) for section in config.sections()})

def apply_configuration(config):

    global G_MIN_WORD_DRAIN_DELAY
    global G_MAX_INTER_WORD_DURATION
    global G_MAX_SUBTITLE_LINE_DURATION
    global G_MAX_CHARS_IN_SUB_ROW
    global G_MAX_WORDS_TO_SEARCH
    global G_STREAMING_LIMIT
    global G_IFLAGS_EXIT_ON_ZERO_SIZE
    global G_IFLAGS_LAST_LOG_TIME_QUANTA_MS
    global G_OFLAGS_APPEND_MODE
    global G_OFLAGS_APPEND_NULL_CHAR

    if (not G_GCP_AUTH_PATH_CFG_NAME in config[G_FILES_SECTION_NAME]):
        config.set(G_FILES_SECTION_NAME, G_GCP_AUTH_PATH_CFG_NAME, "")

    if (not G_PHRASES_PATH_CFG_NAME in config[G_FILES_SECTION_NAME]):
        config.set(G_FILES_SECTION_NAME, G_PHRASES_PATH_CFG_NAME, "")

    if (not G_ENABLE_DEBUG_RESPONSE_DUMP in config[G_FILES_SECTION_NAME]):
        config.set(G_FILES_SECTION_NAME, G_ENABLE_DEBUG_RESPONSE_DUMP, "")

    if (not G_DEBUG_RESPONSE_DUMP_PATH in config[G_FILES_SECTION_NAME]):
        config.set(G_FILES_SECTION_NAME, G_DEBUG_RESPONSE_DUMP_PATH, "")

    if (G_TRANSLATION_SECTION_NAME in config):

        if (G_MIN_WORD_DRAIN_DELAY_NAME in config[G_TRANSLATION_SECTION_NAME]):
            stt_globals.G_MIN_WORD_DRAIN_DELAY = config[G_TRANSLATION_SECTION_NAME].getfloat(G_MIN_WORD_DRAIN_DELAY_NAME)

        if (G_MAX_INTER_WORD_DURATION_NAME in config[G_TRANSLATION_SECTION_NAME]):
            stt_globals.G_MAX_INTER_WORD_DURATION = config[G_TRANSLATION_SECTION_NAME].getint(G_MAX_INTER_WORD_DURATION_NAME)

        if (G_MAX_SUBTITLE_LINE_DURATION_NAME in config[G_TRANSLATION_SECTION_NAME]):
            stt_globals.G_MAX_SUBTITLE_LINE_DURATION = config[G_TRANSLATION_SECTION_NAME].getint(G_MAX_SUBTITLE_LINE_DURATION_NAME)

        if (G_MAX_CHARS_IN_SUB_ROW_NAME in config[G_TRANSLATION_SECTION_NAME]):
            stt_globals.G_MAX_CHARS_IN_SUB_ROW = config[G_TRANSLATION_SECTION_NAME].getint(G_MAX_CHARS_IN_SUB_ROW_NAME)

        if (G_MAX_WORDS_TO_SEARCH_NAME in config[G_TRANSLATION_SECTION_NAME]):
            stt_globals.G_MAX_WORDS_TO_SEARCH = config[G_TRANSLATION_SECTION_NAME].getint(G_MAX_WORDS_TO_SEARCH_NAME)

    if (G_IFLAGS_SECTION_NAME in config):

        if (G_IFLAGS_EXIT_ON_ZERO_SIZE_NAME in config[G_IFLAGS_SECTION_NAME]):
            G_IFLAGS_EXIT_ON_ZERO_SIZE = config[G_IFLAGS_SECTION_NAME].getboolean(G_IFLAGS_EXIT_ON_ZERO_SIZE_NAME)

        if (G_IFLAGS_LAST_LOG_TIME_QUANTA_MS_NAME in config[G_IFLAGS_SECTION_NAME]):
            G_IFLAGS_LAST_LOG_TIME_QUANTA_MS = config[G_IFLAGS_SECTION_NAME].getint(G_IFLAGS_LAST_LOG_TIME_QUANTA_MS_NAME)

    if (G_OFLAGS_SECTION_NAME in config):

        if (G_OFLAGS_APPEND_MODE_NAME in config[G_OFLAGS_SECTION_NAME]):
            G_OFLAGS_APPEND_MODE = config[G_OFLAGS_SECTION_NAME].getboolean(G_OFLAGS_APPEND_MODE_NAME)
        if (G_OFLAGS_APPEND_NULL_CHAR_NAME in config[G_OFLAGS_SECTION_NAME]):
            G_OFLAGS_APPEND_NULL_CHAR = config[G_OFLAGS_SECTION_NAME].getboolean(G_OFLAGS_APPEND_NULL_CHAR_NAME)

def dump_parameters():

    eprint("#--- Fixed Audio recording parameters ---")
    eprint("G_BYTE_PER_SAMPLE = ", G_BYTE_PER_SAMPLE)
    eprint("G_AUD_SAMPLING_RATE = ", G_AUD_SAMPLING_RATE)
    eprint("G_CHUNK_MS = ", G_CHUNK_MS)
    eprint("G_CHUNK_SIZE_BYTES = ", G_CHUNK_SIZE_BYTES)

    eprint("#--- Fixed Input packet parameters ---")
    eprint("G_AUDIO_HEADER_LEN = ", G_AUDIO_HEADER_LEN)

    eprint("#--- Translation process parameters ---")
    eprint("G_MIN_WORD_DRAIN_DELAY = ", stt_globals.G_MIN_WORD_DRAIN_DELAY)
    eprint("G_MAX_INTER_WORD_DURATION = ", stt_globals.G_MAX_INTER_WORD_DURATION)
    eprint("G_MAX_SUBTITLE_LINE_DURATION = ", stt_globals.G_MAX_SUBTITLE_LINE_DURATION)
    eprint("G_MAX_CHARS_IN_SUB_ROW = ", stt_globals.G_MAX_CHARS_IN_SUB_ROW)
    eprint("G_MAX_WORDS_TO_SEARCH = ", stt_globals.G_MAX_WORDS_TO_SEARCH)
    eprint("G_STREAMING_LIMIT = ", G_STREAMING_LIMIT)
    eprint("G_MAX_AUDIO_BUFFER = ", G_MAX_AUDIO_BUFFER)

def usage():
    eprint("TODO: usage")

if __name__ == '__main__':

    global G_EXIT_FLAG
    opt_cfg_path = ""
    opt_verbose = False
    opt_no_run = False
    opt_input_audio = ""
    opt_output_srt  = ""
    opt_dump_gcp_response  = ""

    parser = argparse.ArgumentParser()

    parser.add_argument('-i', '--input_audio', default="/dev/stdin",
            help="path to input audio fifo")

    parser.add_argument('-o', '--output_srt', default="/dev/stdout",
            help="path to output srt fifo")

    parser.add_argument('-c', '--conf', default="stt_cfg.ini",
            help="path to stt_cfg.ini", required=True)
    
    parser.add_argument('-a', '--gcp_auth_path', default="",
            help="path to GCP auth file")

    parser.add_argument('-d', '--dump_gcp_response', default="",
            help="Dump Google STT respnse to this file.")

    parser.add_argument('-L', '--logger_stream', default="stderr",
            help="Set logger to log to syslog or stderr(default)")

    parser.add_argument('-v', '--verbose', action="store_true",
            default=False, help="Verbose")

    parser.add_argument('-n', '--norun', action="store_true",
            default=False, help="Dry Run")

    args = parser.parse_args ()

    opt_cfg_path    = args.conf
    opt_verbose     = args.verbose
    opt_no_run      = args.norun
    opt_input_audio = args.input_audio
    opt_output_srt  = args.output_srt
    opt_gcp_auth_path = args.gcp_auth_path
    opt_dump_gcp_response = args.dump_gcp_response
    stt_globals.G_LOGGER_STREAM = args.logger_stream
    
    if (not os.path.isfile (opt_cfg_path)):
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

    if opt_gcp_auth_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = opt_gcp_auth_path
    else:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = config[G_FILES_SECTION_NAME].get(G_GCP_AUTH_PATH_CFG_NAME)

    if not opt_dump_gcp_response:
        if config[G_FILES_SECTION_NAME].get(G_ENABLE_DEBUG_RESPONSE_DUMP).lower() == 'true':
            opt_dump_gcp_response = config[G_FILES_SECTION_NAME].get(G_DEBUG_RESPONSE_DUMP_PATH)

    while not G_EXIT_FLAG:
        try:
            main(opt_input_audio,
                 opt_output_srt,
                 config[G_FILES_SECTION_NAME].get(G_PHRASES_PATH_CFG_NAME),
                 opt_dump_gcp_response)
        except KeyboardInterrupt:
            G_EXIT_FLAG = True
            sys.exit(0)
        except:
            eprint(traceback.format_exc())
            sys.exit(1)
    eprint ("### Exited Main")
    os._exit(0)
