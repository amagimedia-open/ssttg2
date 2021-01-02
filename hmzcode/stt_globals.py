import sys
from datetime import datetime, timedelta

G_EXIT_FLAG = False

# Audio recording parameters
G_BYTE_PER_SAMPLE = 2
G_AUD_SAMPLING_RATE = 16000
G_CHUNK_MS = 32
G_CHUNK_SIZE_BYTES = int(G_AUD_SAMPLING_RATE / 1000 * G_CHUNK_MS * G_BYTE_PER_SAMPLE)

G_TIMEOUT_SECONDS = 3
G_TIMEOUT_MSECONDS = G_TIMEOUT_SECONDS*1000
G_REPEAT_SUB_THREASHOLD_MS = 1000
G_WRITE_AFTER_CHARACTERS_RECVD = 150
G_MAX_SUB_CHARS = 30
G_STREAMING_LIMIT = 240000 # 280 seconds, as 300 is max limit
G_MAX_AUDIO_BUFFER = 1000 / G_CHUNK_MS # 5 sec
G_AUDIO_HEADER_LEN = 14 # 4 sync + 8 pts + 2 len
G_MIN_SUB_DURATION_MS = 400 # ms
G_MAX_SUB_DURATION_MS = 4000 # ms


## NEW ONES ### 16/09/20
G_RESP_LIST_WORD_INDX = 0
G_RESP_LIST_WORD_TIME_INDX = 1
G_RESP_LIST_WORD_CNSMD_INDX = 2
G_RESP_LIST_WORD_MTIME_INDX = 3

G_MIN_WORD_DRAIN_DELAY = 3.0 #Drain words that are 3 seconds older.
G_MAX_INTER_WORD_DURATION = 800 # 800 ms
G_MAX_SUBTITLE_LINE_DURATION = 1500 # 1500 ms

G_MAX_CHARS_IN_SUB_ROW = 30 ## CC-608 limit
G_MAX_WORDS_TO_SEARCH = 4

G_IFLAGS_EXIT_ON_ZERO_SIZE = False
G_IFLAGS_LAST_LOG_TIME_QUANTA_MS = 5
G_OFLAGS_APPEND_MODE = False
G_OFLAGS_APPEND_NULL_CHAR = True
G_LOGGER_STREAM = "stderr"

main_logger = None

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
    sys.stderr.flush()

def now_2_epochms():
    #https://stackoverflow.com/questions/27245488/converting-iso-8601-date-time-to-seconds-in-python
    #eg: 1984-06-02T19:05:00.000Z
    utc_dt = datetime.utcnow()
    timestamp = (utc_dt - datetime(1970, 1, 1)).total_seconds()
    return int (timestamp * 1000)

