from __future__ import division

import re
import os
import sys
import time 
import threading
import queue
import traceback
from   datetime import datetime

import google
from google.cloud import speech
#from google.cloud.speech import enums
#from google.cloud.speech import types

import stt_commons as comn
import amg_logger  as logr
import stt_globals as glbl

class PacketizedPCMReader(threading.Thread):

    @staticmethod
    def audio_header_get_pts (data):
        return int.from_bytes(data[4:12], byteorder='little')

    @staticmethod
    def audio_header_get_data_length (data):
        return int.from_bytes(data[12:14], byteorder='little')

    def __init__ (self, q):
        threading.Thread.__init__(self)
        self.threadID = glbl.G_PACKPCM_READER_THREAD_ID
        self.name = glbl.G_PACKPCM_READER_THREAD_NAME

        self.fname = glbl.G_INPUT_AUDIO_PATH
        self.fp = open (self.fname, mode="rb")
        self.chunk = glbl.G_CHUNK_SIZE_BYTES 
        self.q = q
        self.last_log_time = time.time()
        self.data_read = 0
        self.logger = logr.amagi_logger (
                        "com.amagi.stt.packpcm_reader",
                        logr.LOG_INFO, 
                        log_stream=glbl.G_LOGGER_STREAM)

    def get_sync_byte_position (self, data):
        sync_byte = 'c0ffeeee'
        # /2 as 0xff is one byte but ff are two chars
        return int(data.hex().find (sync_byte)/2)

    def re_align (self,old_data, sync_pos):
        if len(old_data) - sync_pos >= glbl.G_AUDIO_HEADER_LEN:
            data_len = PacketizedPCMReader.audio_header_get_data_length (old_data[sync_pos:])
            old_data_len = len (old_data) - sync_pos - glbl.G_AUDIO_HEADER_LEN
            self.logger.info (f"{data_len} ol={old_data_len}")
            new_data = self.fp.read (data_len-old_data_len)
            final_data = old_data[sync_pos:] + new_data
            self.q.put (final_data)
        
    def run (self):
        self.logger.info (f"{self.name} thread starting")

        while not glbl.G_EXIT_FLAG:
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
                    self.logger.info (f"Re-aligning ...{pos}...{data[pos:pos+5].hex()}...{PacketizedPCMReader.audio_header_get_pts (data[pos:])}..")
                    self.re_align (data, pos)
                    continue
            #else:
            #    print ('Got syncbyte')
            if (PacketizedPCMReader.audio_header_get_data_length (data)) == 0:
                self.logger.info ("Received audio packet with length=0")
                if (glbl.G_IFLAGS_EXIT_ON_ZERO_SIZE):
                    glbl.G_EXIT_FLAG = True
                    break

            self.q.put (data)

        self.logger.info (f"{self.name} thread ending")

