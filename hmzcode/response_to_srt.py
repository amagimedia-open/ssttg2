import re
import os
import sys
import time 
import threading
import queue
import traceback
from collections import OrderedDict
import stt_globals
import amg_logger
from stt_google_response_interface import *

def milliseconds_to_HMS (ms):
    #ms -= 1000
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

class ResponseToSRT (threading.Thread):
    def __init__(self, threadID, name, q,srt_fname, append_mode, \
            append_null_char, dump_gcp_response = ""):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.q = q
        self.exit_flag = False
        self.dump_gcp_response = dump_gcp_response
        self.logger = amg_logger.amagi_logger ("com.amagi.stt.resp_to_srt", amg_logger.LOG_INFO, log_stream=stt_globals.G_LOGGER_STREAM)
        if append_mode:
            self.open_mode = "a"
        else:
            self.open_mode = "w"
        if append_null_char:
            self.null_char = "\0"
        else:
            self.null_char = ""
        self.last_rcvd_epoch = 0
        self.srt_count = 0
        self.srt_fname = srt_fname
        self.last_srt_sub = []#[tcin,tcout,text]
        self.last_consumed_pts = 0

        self.first_response_time = 0
        self.words_list = []#[ (word, epoch_time_rcvd_at, is consumed, timestamp), ()... ]
  
    def srt_writer (self, text, tc_in, duration_ms):
        with open (self.srt_fname, self.open_mode) as fp:
            self.srt_count += 1
            srt_text = f"{self.srt_count}\n"
            #fp.write (f"{self.srt_count}\n")
            if False:#len(self.last_srt_sub) > 0 and (tc_in-self.last_srt_sub[1] < stt_globals.G_REPEAT_SUB_THREASHOLD_MS):
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
            fp.write (srt_text.encode ('ascii', 'ignore').decode('ascii').upper()+self.null_char)
            self.logger.info (srt_text.replace("\n", " "))#.encode('utf-8'))
            #self.logger.info (srt_text.encode('utf-8'))
            self.last_srt_sub = [tc_in, tc_in+duration_ms, text]

    def get_duration (self, wr_list):
        duration = wr_list[-1] - wr_list[0]
        # < 0.9 to avoid accounting for microseconds added to 
        # distinguish words with same wird-time-offset.
        duration = duration if duration > 0.9 else stt_globals.G_MAX_INTER_WORD_DURATION
        return duration
    
    def can_consume_subtitle (self, time_now):

        if len (self.words_list) == 0 or \
          self.words_list[-1][stt_globals.G_RESP_LIST_WORD_CNSMD_INDX]:
            # last word is consumed.
            return False

        min_timeout_since_last_word = max (1.5, \
                stt_globals.G_MIN_WORD_DRAIN_DELAY - stt_globals.G_MAX_SUBTITLE_LINE_DURATION/1000.0)
        last_word_time = self.words_list[-1][stt_globals.G_RESP_LIST_WORD_MTIME_INDX]
        for it in self.words_list:
            if not it[stt_globals.G_RESP_LIST_WORD_CNSMD_INDX]:
                # if last-word-time - fist-unconsumed-word-time > Threshold or
                # if curr-sys-time - first-unconsumed-word-time > Threshold
                # then consumed 'em.
                if last_word_time - it[stt_globals.G_RESP_LIST_WORD_MTIME_INDX] >= (1000.0*stt_globals.G_MIN_WORD_DRAIN_DELAY) or \
                    time_now - it[stt_globals.G_RESP_LIST_WORD_TIME_INDX] >= min_timeout_since_last_word:
                    self.logger.debug ("mtime diff= %d > global:%d, epoch_diff = %d" %(\
                            last_word_time - it[stt_globals.G_RESP_LIST_WORD_MTIME_INDX],\
                            stt_globals.G_MIN_WORD_DRAIN_DELAY, \
                            time_now - it[stt_globals.G_RESP_LIST_WORD_TIME_INDX]))
                    return True
        return False

    def write (self):
        text = ""
        wr_list = []
        duration_ms = 0
        for it in self.words_list:
            if not it[stt_globals.G_RESP_LIST_WORD_CNSMD_INDX]:

                if (len (text.strip()) + len (it[stt_globals.G_RESP_LIST_WORD_INDX]) + 1) > \
                    stt_globals.G_MAX_CHARS_IN_SUB_ROW:
                    # Case where single word len > line-length.
                    if len (text) == 0:
                        self.logger.warn ("Chopping off word larger than 32 charaters !! - word=" \
                                + it[stt_globals.G_RESP_LIST_WORD_INDX].encode('utf-8'))
                        it[stt_globals.G_RESP_LIST_WORD_CNSMD_INDX] = True
                        self.last_consumed_pts = it[stt_globals.G_RESP_LIST_WORD_MTIME_INDX]
                        text = text + it[stt_globals.G_RESP_LIST_WORD_INDX] + " "
                        text = text[:stt_globals.G_MAX_CHARS_IN_SUB_ROW]
                        wr_list.append (it)
                    # write the SRT.
                    duration_ms = self.get_duration ([i[stt_globals.G_RESP_LIST_WORD_MTIME_INDX] for i in wr_list])
                    self.srt_writer (text.strip(), wr_list[0][stt_globals.G_RESP_LIST_WORD_MTIME_INDX], duration_ms)
                    return
                else:
                    # Accumulate the line.
                    if len(wr_list) > 0 and \
                       (it[stt_globals.G_RESP_LIST_WORD_MTIME_INDX] - \
                          wr_list[0][stt_globals.G_RESP_LIST_WORD_MTIME_INDX] > \
                          stt_globals.G_MAX_SUBTITLE_LINE_DURATION or \
                        it[stt_globals.G_RESP_LIST_WORD_MTIME_INDX] - \
                          wr_list[-1][stt_globals.G_RESP_LIST_WORD_MTIME_INDX] > \
                          stt_globals.G_MAX_INTER_WORD_DURATION):
                            break
                    wr_list.append (it)
                    text = text + it[stt_globals.G_RESP_LIST_WORD_INDX] + " "
                    it[stt_globals.G_RESP_LIST_WORD_CNSMD_INDX] = True
                    self.last_consumed_pts = it[stt_globals.G_RESP_LIST_WORD_MTIME_INDX]
        # will come here when very less text is there to be written.
        # can happen on timeout/long pause or on is_final=True
        if len (text.strip ()) > 0:
            # write the SRT.
            duration_ms = self.get_duration ([i[stt_globals.G_RESP_LIST_WORD_MTIME_INDX] for i in wr_list])
            self.srt_writer (text.strip(), wr_list[0][stt_globals.G_RESP_LIST_WORD_MTIME_INDX], duration_ms)

    def response_to_word_time_offset (self, response, rtime, mapped_time):
        new_response = response.strip().split(" ")
        index = 0
        rl_l = len (self.words_list)
        tl_l = len (new_response)

        #print (response, rtime, mapped_time)
        
        new_words_list = new_response
        is_word_old = []

        pivot_in_old_list = 0
        old_list = self.words_list
        # if pivot in old list is incremented for search, then increment
        # l_max_words_to_search till a next solid match is got.
        l_max_words_to_search = stt_globals.G_MAX_WORDS_TO_SEARCH

        for word in new_response:
            if rl_l == 0:
                break
            local_pivot = pivot_in_old_list
            while (local_pivot < rl_l) and local_pivot - pivot_in_old_list < l_max_words_to_search:
                if word.upper().strip(".").strip(",") == \
                   old_list[local_pivot][stt_globals.G_RESP_LIST_WORD_INDX].upper().strip(".").strip(","):
                    is_word_old.append (True)
                    '''
                    if local_pivot == pivot_in_old_list:#i=0
                        # if match is found then try to set search words to stt_globals.G_MAX_WORDS_TO_SEARCH.
                        l_max_words_to_search -= 1
                        l_max_words_to_search = max (stt_globals.G_MAX_WORDS_TO_SEARCH, l_max_words_to_search)
                    '''
                    if pivot_in_old_list != local_pivot:
                        self.logger.info ("Found match in old list at a later position, diff=%d" %\
                                (local_pivot-pivot_in_old_list))
                        l_max_words_to_search += (local_pivot-pivot_in_old_list)
                    local_pivot += 1
                    pivot_in_old_list = local_pivot
                    break
                else:
                    self.logger.debug ("lp=%d, rl_l=%d, word=%s, old=%s" %(local_pivot, rl_l, word, \
                        old_list[local_pivot][stt_globals.G_RESP_LIST_WORD_INDX].upper()))
                    local_pivot += 1
            else: # Unable to find a word in old words
                is_word_old.append (False)

        if len (is_word_old) > 0 and len (is_word_old) != tl_l:
            self.logger.warn (f"Marked list and word list are not of same length, {len (is_word_old)} != {tl_l}")
            raise (f"Marked list and word list are not of same length")
        #print (self.last_consumed_pts)
        self.logger.debug (str(is_word_old))
        self.words_list = []
        '''
        If the first word changes,then timestamp of all words are updated,
        But if the first word was already consumed, then it's not done.
        '''
        if (rl_l > 0 and not old_list[0][stt_globals.G_RESP_LIST_WORD_CNSMD_INDX] and not is_word_old[0]) or \
            len(is_word_old) == 0:
            #print ("--------------------------")
            # Mark everything with new timestamp.
            for word in new_words_list:
                self.words_list.append ([word, rtime, False, mapped_time])
            return
        
        i = 0
        old_rtime = old_list[i][stt_globals.G_RESP_LIST_WORD_TIME_INDX]
        old_mtime = old_list[i][stt_globals.G_RESP_LIST_WORD_MTIME_INDX]
        prev_mtime = 0
        for word, is_old in zip(new_words_list, is_word_old):
            is_consumed = False
            if is_old and i < rl_l:
                # unchanged words are marked with its own pts.
                old_rtime = old_list[i][stt_globals.G_RESP_LIST_WORD_TIME_INDX]
                old_mtime = old_list[i][stt_globals.G_RESP_LIST_WORD_MTIME_INDX]

            # changed words are marked with pts of the previous word.
            if old_mtime <= self.last_consumed_pts:
                is_consumed = True

            self.words_list.append ([word, old_rtime, is_consumed, old_mtime])
            # See comment below, to have different timestamps.
            old_mtime += 0.001
            i += 1

        # All new words from End are marked with incoming latest timestamp.
        i = len (is_word_old) - 1
        while i >= 0:
            if is_word_old[i]:
                break
            else:
                self.words_list[i][stt_globals.G_RESP_LIST_WORD_TIME_INDX] = rtime
                # +1/1000.0 is to add a few microseconds in order to attach
                # different and increasing timestamps to each word. 
                # If more than two new words come in same response, 
                # we want to give each word different timestamp.
                self.words_list[i][stt_globals.G_RESP_LIST_WORD_MTIME_INDX] = mapped_time + i/1000.0
                self.words_list[i][stt_globals.G_RESP_LIST_WORD_CNSMD_INDX] = False
            i -= 1

        self.logger.debug (str(self.words_list))

    def run(self):
        self.logger.info ("Starting " + self.name)
        loop_count = 0
        while not self.exit_flag:
            try:
                result = stream = None
                stream, result, rtime = self.q.get(timeout=0.1) # 100ms.
            except:
                pass

            time_now = time.time ()
            try:
                if result:
                    if self.dump_gcp_response:
                        with open (self.dump_gcp_response, "a") as fp:
                            #fp.write (str(result).replace("\n", " ") + f"Time:{rtime}")
                            #fp.write (f"\n==FINAL={result.is_final}==\n")
                            fp.write (f"transcript:{result.transcript};; "\
                                      f"stability:{result.stability};; "\
                                      f"end_sec:{result.pts_seconds};; "\
                                      f"end_nanos:{result.pts_nanos};; "\
                                      f"time:{rtime};; "\
                                      f"is_final:{result.is_final}"\
                                      "\n\n")
                            fp.flush ()
                    cur_transcription = result.transcript
                    cur_timestamp = (stream.restart_counter * stt_globals.G_STREAMING_LIMIT) + \
                            result.pts_seconds*1000 + \
                            result.pts_nanos/1000000 - \
                            stream.old_data_sent_ms
                    cur_timestamp = stream.get_mapped_audio_pts (cur_timestamp)

                    self.response_to_word_time_offset (result.transcript, \
                            rtime, cur_timestamp)
                
                if self.can_consume_subtitle (time_now):
                    self.write ()

                if result and result.is_final:
                    self.logger.info (f"=FINAL===={cur_transcription.encode('utf-8')}=====")
                    while len(self.words_list) > 0 and \
                        (not self.words_list[-1][stt_globals.G_RESP_LIST_WORD_CNSMD_INDX]):
                        self.write ()
                        time.sleep (0.05) #50ms sleep, no specific reason.
                
                    self.last_srt_sub = []#[tcin,tcout,text]
                    self.first_response_time = 0
                    self.words_list = [] #[ (word, epoch_time_rcvd_at, is consumed, timestamp), ()... ]
                    self.last_consumed_pts = 0
                    if rtime - self.last_rcvd_epoch > 3.0:
                        self.logger.warn (f"Final response epoch time came {rtime - self.last_rcvd_epoch} "\
                                "secs late than the previous response. This can cause drops.")
                if result:
                    self.last_rcvd_epoch = rtime
            except:
                self.logger.error (traceback.format_exc().replace("\n", " "))
        self.logger.info ("Exiting " + self.name)
