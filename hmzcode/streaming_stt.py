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
from   datetime import datetime
import argparse
from   collections import OrderedDict
import configparser

import google
from   google.cloud import speech
#from google.cloud.speech import enums
#from google.cloud.speech import types

import stt_commons as comn
import amg_logger  as logr
import stt_globals as glbl
import stt_cmdargs as args
import stt_default_config as defconf
from   stt_pcm_stream_state import PCMStreamState
from   stt_packpcm_reader   import PacketizedPCMReader
from   stt_srt_writer       import SRTWriter
from   stt_google_response_interface import *

#----------------------------------------------------------------------------
# looks like the PCMGenerator class has to be in this file
# only, else the google api throws some RPC errors

class PCMGenerator ():
    def __init__ (self, q, pcm_stream_state):
        self.q = q
        self.pcm_stream_state = pcm_stream_state
        self.logger = logr.amagi_logger (
                        "com.amagi.stt.PCMGenerator", 
                        logr.LOG_INFO, 
                        log_stream=glbl.G_LOGGER_STREAM)
        self.logger.info ("PCMGenerator initialized")

    def parse_audio_packet (self, data):
        if data and data[0:4].hex() != 'c0ffeeee':
            exception_str = f"Could not get Sync bytes. Aborting...{data[0:4].hex()}"
            self.logger.error(exception_str)
            raise Exception(exception_str)

        #print (f"{data[4:9].hex()} ========")
        pts = PacketizedPCMReader.audio_header_get_pts (data)
        data_len = PacketizedPCMReader.audio_header_get_data_length (data)
        running_pts = (self.pcm_stream_state.restart_counter * glbl.G_STREAMING_LIMIT) + self.pcm_stream_state.consumed_ms

        #print (f"add map[{running_pts}] = {pts}")
        if (pts > 0):
            self.logger.info(f"Received-data: pts={pts}, len={data_len}")
        
        self.pcm_stream_state.audio_pts_map_lock.acquire ()
        self.pcm_stream_state.audio_pts_map[running_pts] = pts
        self.pcm_stream_state.audio_pts_map_lock.release ()
        #print (f"pts:{pts} len:{data_len} {len(data[glbl.G_AUDIO_HEADER_LEN:data_len+G_AUDIO_HEADER_LEN])}========")
        #print(data[10:data[9]])
        return data[glbl.G_AUDIO_HEADER_LEN : data_len+glbl.G_AUDIO_HEADER_LEN]

    def get_bytes (self):

        data = self.pcm_stream_state.get_data_from_pts ()
        if data:
            yield data

        while not glbl.G_EXIT_FLAG and \
              self.pcm_stream_state.consumed_ms < glbl.G_STREAMING_LIMIT:

            #try:
            data = self.parse_audio_packet (self.q.get ())
            self.pcm_stream_state.push_to_sent_q (data)
            self.pcm_stream_state.incr_consumed_ms(glbl.G_CHUNK_MS)
            yield data

            #except:
            #    glbl.main_logger.error(traceback.format_exc())
            #    break
            #    #os._exit(1)

        self.logger.info (f"PCMGenerator ending, bytes put = {self.pcm_stream_state.consumed_ms}")

#----------------------------------------------------------------------------

class Transcriber():

    #+---------------------------------------------------------------------+
    #|                                      (thread) PacketizedPCMReader   |
    #|                                                       V             |
    #|                                                   [ pcm_q ]         |
    #|                                                       V             |
    #|                                   requests      ( PCMGenerator )    |
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

    @staticmethod
    def create_speech_config():

        phrases = []

        if (len(glbl.G_PHRASES_PATH) != 0):
            with open (glbl.G_PHRASES_PATH, "r", encoding=glbl.G_PHRASES_ENCODING) as fp:
                for line in fp:
                    if line:
                        phrases.append (line.strip().encode ('ascii', 'ignore').decode('ascii'))
        else:
            glbl.main_logger.info(f"Phrases file {glbl.G_PHRASES_PATH} is null.")

        glbl.main_logger.info(f"Number of phrases as context = {len(phrases)}")

        speech_context = speech.SpeechContext(phrases=phrases[:glbl.G_MAX_PHRASES])

        config = speech.RecognitionConfig(
                    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                    sample_rate_hertz=glbl.G_AUD_SAMPLING_RATE,
                    enable_word_time_offsets=False,
                    model='video',
                    profanity_filter=True,
                    enable_automatic_punctuation=True,
                    speech_contexts=[speech_context],
                    language_code=glbl.G_LANGUAGE_CODE)

        speech_config = speech.StreamingRecognitionConfig(
                            config=config,
                            interim_results=True)

        return speech_config


    def queue_transcription_responses(self):
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
        for response in self.responses:
            if self.pcm_stream_state.consumed_ms >= glbl.G_STREAMING_LIMIT:
                #pcm_stream_state.stream_time = get_current_time ()
                glbl.main_logger.info(f"timeout breaking out of responses loop,"
                                  "consumed_ms={self.pcm_stream_state.consumed_ms}")
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
            self.transcription_response_q.put ([self.pcm_stream_state, amg_result, time_now])

            result_end_time_ms = result.result_end_time.seconds*1000 + \
                                 result.result_end_time.microseconds/1000
            self.pcm_stream_state.update_last_sub_pts (result_end_time_ms)

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


    def perform_transcription (self):

        while not glbl.G_EXIT_FLAG:

            glbl.main_logger.info(f"starting transcription iteration")

            try:
                # creating a generator using data supplied by PacketizedPCMReader
                generator_obj = PCMGenerator (self.pcm_q, self.pcm_stream_state)
                audio_generator = generator_obj.get_bytes()

                for data in audio_generator:    #blocks until there is data
                    break                       #in the audio_generator 

                # the transcription request stream (via a generator)
                requests = (speech.StreamingRecognizeRequest(audio_content=content)
                            for content in audio_generator)

                # the transcription response stream (via a generator)
                self.responses = self.speech_client.streaming_recognize (
                                self.speech_config, requests)

                # forwarding responses to a 'q' that is read/handled by SRTWriter
                self.queue_transcription_responses ()

                # control comes here when there are no more responses
                # this can happen if
                #   (a) there is no more input (or)
                #   (b) streaming_recognize cannot process more than this duration
                #       (in which case we need to set the pcm_stream_state right
                #        and begin all over again)

                self.pcm_stream_state.on_iteration_complete()

                glbl.main_logger.info("=====RETRY AFTER 5MIN====="
                                 "last_sent={self.pcm_stream_state.last_sub_pts}")

                lk = self.pcm_stream_state.get_last_key()
                if (lk != None):
                    glbl.main_logger.info(f"=====audio_pts_map[{lk}] = "
                         "{self.pcm_stream_state.audio_pts_map[lk]}======")

            except google.api_core.exceptions.ServiceUnavailable:

                glbl.main_logger.info("=====ServiceUnavailable exception.===RETRY=====")
                time.sleep (glbl.G_RETRY_DURATION_SEC_ON_SERVICE_UNAVAILABLE)


    def terminate(self):

        glbl.G_EXIT_FLAG = True


    def await_termination(self):

        if (self.srt_writer.is_alive()):
            glbl.main_logger.info ("waiting for srt_writer to end")
            self.srt_writer.join()
            glbl.main_logger.info ("srt_writer ended")
           
        if (self.packpcm_reader.is_alive()):
            glbl.main_logger.info ("waiting for packpcm_reader to end")
            self.packpcm_reader.join()
            glbl.main_logger.info ("packpcm_reader ended")

        glbl.main_logger.info ("await_termination() completed")


    def __init__(self):

        # speech api objects
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = glbl.G_GCP_AUTH_PATH
        self.speech_client = speech.SpeechClient()
        self.speech_config = Transcriber.create_speech_config()

        # pcm stream state across speech_client.streaming_recognize invocations
        self.pcm_stream_state = PCMStreamState()

        # the queues
        self.transcription_response_q = queue.Queue ()
        self.pcm_q = queue.Queue (maxsize=glbl.G_MAX_AUDIO_BUFFER)

        # the threads
        self.srt_writer     = SRTWriter (self.transcription_response_q)
        self.packpcm_reader = PacketizedPCMReader (self.pcm_q)


    def run(self):

        self.srt_writer.start ()

        self.packpcm_reader.start ()

        self.perform_transcription ()


#----------------------------------------------------------------------------

if __name__ == '__main__':

    transcriber = None
    glbl.main_logger = None

    try:

        (dump_def_config, cp) = args.gen_config_from_cmdargs (sys.argv[1:])

        if (dump_def_config):
            comn.eprint(defconf.stt_default_config_str)
            os._exit(0)

        glbl.config_2_globals(cp)

        if (glbl.G_VERBOSE):
            glbl.dump_globals()

        if (glbl.G_NO_RUN):
            os._exit(0)

        glbl.main_logger = logr.amagi_logger (
                      "com.amagi.stt.main", 
                      logr.LOG_INFO, 
                      log_stream=glbl.G_LOGGER_STREAM)


        transcriber = Transcriber()
        transcriber.run()

        glbl.main_logger.info ("### Ending transcribe normally")

    except Exception as e:
        #except google.auth.exceptions.DefaultCredentialsError:
        #except FileNotFoundError:

        if (glbl.main_logger != None):
            glbl.main_logger.error(traceback.format_exc())
        if (transcriber != None):
            transcriber.terminate()

    except KeyboardInterrupt:

        if (glbl.main_logger != None):
            glbl.main_logger.error("KeyboardInterrupt")
        if (transcriber != None):
            transcriber.terminate()

    finally:

        if (transcriber != None):
            transcriber.await_termination()

    os._exit(0)

