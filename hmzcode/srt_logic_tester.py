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
import argparse
from collections import OrderedDict
import configparser
import json
from copy import deepcopy

import google
from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types

from response_to_srt import ResponseToSRT
from stt_data_structure import StreamDataStructure
from stt_globals import *
from stt_google_response_interface import *

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print (f"Usage: {sys.argv[0]} <input log> <output srt>")
        sys.exit (1)
    q_obj = queue.Queue ()
    thread_obj = ResponseToSRT (1, "audio_to_srt_1", q_obj, sys.argv[2],
            True, False)
    thread_obj.start ()
    stream_obj = StreamDataStructure ()
    time_off = 0.0
    time_l = 0
    
    i=0
    while i < 60*60*1000:
        stream_obj.audio_pts_map[i] = i
        i = i + 200

    try:
        with open(sys.argv[1]) as fp:
            try:
                for line in fp:
                    m = re.search (".*transcript:(.*);; stability:(.*);; end_sec:([0-9]*);; end_nanos:([0-9]*);; time:([\.0-9]*);; is_final:([FTa-z]*)", line)
                    if m:
                        #result = "{\"alternatives\":{\"transcript\": %s, \"stability\": %s, \"result_end_time\" : { \"seconds\": %s, \"nanos\": %s } }" %(\
                        #    m.groups()[0], m.groups()[1], m.groups()[2], m.groups()[3])
                        #print(result, flush=True)
                        #result = json.loads (result)
                        amg_result = ResponeInterface ()
                        amg_result.transcript     = m.groups()[0]
                        amg_result.stability      = float(m.groups()[1])
                        amg_result.pts_seconds    = int(m.groups()[2])
                        amg_result.pts_nanos      = int(m.groups()[3])
                        time_l = float(m.groups()[4])
                        time_now = time.time ()
                        if time_off == 0.0:
                            time_off = time_now - time_l
                            print (f"=====time_off={time_off} ====n={time_now}==l={time_l}====={m.groups()[4]}====")
                        elif time_now < time_l + time_off:
                            time.sleep (time_l + time_off - time_now)
                        
                        amg_result.is_final       = True if m.groups()[5] == "True" else False
                        #print ("q.put = " + str(result) + "--" + str(time_l+time_off), flush=True)
                        q_obj.put ([stream_obj, deepcopy(amg_result), time_l+time_off])
                    #time.sleep (0.01)
            except:
                print(traceback.format_exc(), flush=True)
                os._exit (1)
    except:
        print(traceback.format_exc(), flush=True)

    thread_obj.join ()
