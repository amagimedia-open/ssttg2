import threading
import queue
import time
import traceback
from collections import OrderedDict
from stt_globals import *

def get_current_time():
    """Return Current Time in MS."""

    return int(round(time.time() * 1000))

class PCMStreamState ():
    def __init__ (self):
        self.stream_time = get_current_time ()
        self.restart_counter = 0
        self._consumed_ms = 0
        self.last_iter_consumed_ms = 0
        self.max_sent_audio_q_len = 500 / G_CHUNK_MS
        self.sent_audio_q = queue.Queue ()
        self.sent_q_head_pts = 0
        self._last_sub_pts = 0
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
        pts = self._last_sub_pts + (self.restart_counter-1) * G_STREAMING_LIMIT
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
      
    def on_iteration_complete (self):
        self.restart_counter += 1
        self.last_iter_consumed_ms += self._consumed_ms
        self._consumed_ms = 0

    def update_last_sub_pts (self, result_end_time_ms):
        self._last_sub_pts = \
            result_end_time_ms - self.old_data_sent_ms

    @property
    def consumed_ms(self):
        return self._consumed_ms

    def incr_consumed_ms(self, val):
        self._consumed_ms += val

    @property
    def last_sub_pts(self):
        return self._last_sub_pts

    def get_last_key(self):
        lk = None
        if len(self.audio_pts_map.keys ()) > 0:
            lk = list(self.audio_pts_map.keys ())[-1]
        return lk

