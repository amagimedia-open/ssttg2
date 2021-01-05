import sys
from datetime import datetime, timedelta

import amg_logger

#+----------------------------+
#| Audio recording parameters |
#+----------------------------+

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

#+-----------------------+
#| NEW ONES ### 16/09/20 |
#+-----------------------+

G_RESP_LIST_WORD_INDX = 0
G_RESP_LIST_WORD_TIME_INDX = 1
G_RESP_LIST_WORD_CNSMD_INDX = 2
G_RESP_LIST_WORD_MTIME_INDX = 3

#+----------------------------------+
#| Variables set from configuration |
#+----------------------------------+

# [FILES] section in config file

G_INPUT_AUDIO_PATH = ""
G_OUTPUT_SRT_PATH  = ""
G_GCP_AUTH_PATH    = ""
G_PHRASES_PATH     = ""

# [TRANSLATION] section in config file

G_MIN_WORD_DRAIN_DELAY = 3.0 #Drain words that are 3 seconds older.
G_MAX_INTER_WORD_DURATION = 800 # 800 ms
G_MAX_SUBTITLE_LINE_DURATION = 1500 # 1500 ms
G_MAX_CHARS_IN_SUB_ROW = 30 ## CC-608 limit
G_MAX_WORDS_TO_SEARCH = 4

# [IFLAGS] section in config file

G_IFLAGS_EXIT_ON_ZERO_SIZE = False
G_IFLAGS_LAST_LOG_TIME_QUANTA_MS = 5

# [OFLAGS] section in config file

G_OFLAGS_APPEND_MODE = False
G_OFLAGS_APPEND_NULL_CHAR = True

# [LOGGING] section in config file

G_VERBOSE = False
G_LOGGER_STREAM = "stderr"

# [OTHERS] section in config file

G_NO_RUN = False

#+------------------------+
#| Other global variables |
#+------------------------+

G_EXIT_FLAG = False
main_logger = None

#+------------------+
#| HELPER FUNCTIONS |
#+------------------+

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
    sys.stderr.flush()

def now_2_epochms():
    #https://stackoverflow.com/questions/27245488/converting-iso-8601-date-time-to-seconds-in-python
    #eg: 1984-06-02T19:05:00.000Z
    utc_dt = datetime.utcnow()
    timestamp = (utc_dt - datetime(1970, 1, 1)).total_seconds()
    return int (timestamp * 1000)

def config_2_globals(cp):

    #+--------------------------+
    #| declare global variables |
    #+--------------------------+

    # [FILES] section in config file

    global G_INPUT_AUDIO_PATH
    global G_OUTPUT_SRT_PATH
    global G_GCP_AUTH_PATH
    global G_PHRASES_PATH

    # [TRANSLATION] section in config file

    global G_MIN_WORD_DRAIN_DELAY
    global G_MAX_INTER_WORD_DURATION
    global G_MAX_SUBTITLE_LINE_DURATION
    global G_MAX_CHARS_IN_SUB_ROW
    global G_MAX_WORDS_TO_SEARCH

    # [IFLAGS] section in config file

    global G_IFLAGS_EXIT_ON_ZERO_SIZE
    global G_IFLAGS_LAST_LOG_TIME_QUANTA_MS

    # [OFLAGS] section in config file

    global G_OFLAGS_APPEND_MODE
    global G_OFLAGS_APPEND_NULL_CHAR

    # [LOGGING] section in config file

    global G_VERBOSE
    global G_LOGGER_STREAM

    # [OTHERS] section in config file

    global G_NO_RUN

    #+----------------------+
    #| set global variables |
    #+----------------------+

    #[FILES] section

    G_INPUT_AUDIO_PATH = cp.get("FILES", "input_audio_path")
    G_OUTPUT_SRT_PATH  = cp.get("FILES", "output_srt_path")
    G_GCP_AUTH_PATH    = cp.get("FILES", "gcp_auth_path")
    G_PHRASES_PATH     = cp.get("FILES", "phrases_path")

    #[TRANSLATION] section

    G_MIN_WORD_DRAIN_DELAY       = cp.getfloat("TRANSLATION", "min_word_drain_delay_sec")
    G_MAX_INTER_WORD_DURATION    = cp.getint  ("TRANSLATION", "max_inter_word_duration_ms")
    G_MAX_SUBTITLE_LINE_DURATION = cp.getint  ("TRANSLATION", "max_subtitle_line_duration_ms")
    G_MAX_CHARS_IN_SUB_ROW       = cp.getint  ("TRANSLATION", "max_chars_in_sub_row")
    G_MAX_WORDS_TO_SEARCH        = cp.getint  ("TRANSLATION", "max_words_to_search")

    #[IFLAGS] section

    G_IFLAGS_EXIT_ON_ZERO_SIZE       = cp.getboolean ("IFLAGS", "exit_on_zero_size")
    G_IFLAGS_LAST_LOG_TIME_QUANTA_MS = cp.getint     ("IFLAGS", "last_log_time_quanta_ms")

    #[OFLAGS] section

    G_OFLAGS_APPEND_MODE      = cp.getboolean ("OFLAGS", "append_mode")
    G_OFLAGS_APPEND_NULL_CHAR = cp.getboolean ("OFLAGS", "append_null_char")

    #[LOGGING] section

    G_VERBOSE       = cp.getboolean ("LOGGING", "verbose")
    G_LOGGER_STREAM = cp.get        ("LOGGING", "logger_stream")

    #[OTHERS] section

    G_NO_RUN = cp.getboolean ("OTHERS", "no_run")


def dump_globals():

    logger = amg_logger.amagi_logger (
                "com.amagi.stt.globals", 
                amg_logger.LOG_INFO, 
                amg_logger.LOG_USER, 
                G_LOGGER_STREAM)

    for key, value in globals().items():
        if (key.startswith("G_")):
            logger.info(f"{key} = {value}")


