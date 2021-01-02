
import re
import sys
import time 
import threading
import queue


class ReadGen:
    def __init__ (self, inp_file, CHUNK):
        self.fname = inp_file
        #self.fp = open (self.fname, mode="rb")
        self.chunk = CHUNK

    def get_bytes (self):
        with open (self.fname, mode="rb") as fp:
            while True:
                #time.sleep (0.03)
                data = fp.read (self.chunk)
                if not data:
                    break
                yield data

o = ReadGen ("pipe.wav", 1024)                
with open ("o.wav", "wb") as fp:
    for data in o.get_bytes ():
        fp.write (data)
