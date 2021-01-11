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

#+--------+
#| Others |
#+--------+

G_PACKPCM_READER_THREAD_ID    = 1
G_PACKPCM_READER_THREAD_NAME  = "packpcm_reader"
G_PACKPCM_READER_DATA_LOGGING_FREQ_SEC = 5

G_SRT_WRITER_THREAD_ID      = 2
G_SRT_WRITER_THREAD_NAME    = "srt_writer"
G_SRT_WRITER_Q_READ_TIMEOUT = 0.1 #100ms

G_LANGUAGE_CODE    = 'en-US'  # a BCP-47 language tag
G_MAX_PHRASES      = 5000
G_PHRASES_ENCODING = "utf-8"
G_MIN_TRANSCRIPTION_STABILITY = 0.85
G_RETRY_DURATION_SEC_ON_SERVICE_UNAVAILABLE = 5

#+-----------+
#| FUNCTIONS |
#+-----------+

def config_ini_2_vars(cp):

    #+---------------------------------+
    #| create and set global variables |
    #+---------------------------------+

    #[FILES] section

    globals()["G_INPUT_AUDIO_PATH"] = \
            cp.get("FILES", "input_audio_path")
    globals()["G_OUTPUT_SRT_PATH"]  = \
            cp.get("FILES", "output_srt_path")
    globals()["G_PHRASES_PATH"]     = \
            cp.get("FILES", "phrases_path")
    globals()["G_GCP_AUTH_PATH"]    = \
            cp.get("FILES", "gcp_auth_path")

    #[TRANSLATION] section

    globals()["G_MIN_WORD_DRAIN_DELAY"]       = \
            cp.getfloat("TRANSLATION", "min_word_drain_delay_sec")
    globals()["G_MAX_INTER_WORD_DURATION"]    = \
            cp.getint  ("TRANSLATION", "max_inter_word_duration_ms")
    globals()["G_MAX_SUBTITLE_LINE_DURATION"] = \
            cp.getint  ("TRANSLATION", "max_subtitle_line_duration_ms")
    globals()["G_MAX_CHARS_IN_SUB_ROW"]       = \
            cp.getint  ("TRANSLATION", "max_chars_in_sub_row")
    globals()["G_MAX_WORDS_TO_SEARCH"]        = \
            cp.getint  ("TRANSLATION", "max_words_to_search")

    #[IFLAGS] section

    globals()["G_IFLAGS_EXIT_ON_ZERO_SIZE"]       = \
            cp.getboolean ("IFLAGS", "exit_on_zero_size")
    globals()["G_IFLAGS_LAST_LOG_TIME_QUANTA_MS"] = \
            cp.getint     ("IFLAGS", "last_log_time_quanta_ms")

    #[OFLAGS] section

    globals()["G_OFLAGS_APPEND_MODE"]      = \
            cp.getboolean ("OFLAGS", "append_mode")
    globals()["G_OFLAGS_APPEND_NULL_CHAR"] = \
            cp.getboolean ("OFLAGS", "append_null_char")

    #[LOGGING] section

    globals()["G_VERBOSE"]       = \
            cp.getboolean ("LOGGING", "verbose")
    globals()["G_LOGGER_STREAM"] = \
            cp.get        ("LOGGING", "logger_stream")

    #[OTHERS] section

    globals()["G_NO_RUN"] = \
            cp.getboolean ("OTHERS", "no_run")


def dump_config_vars():

    logger = amg_logger.amagi_logger (
                "com.amagi.stt.globals", 
                amg_logger.LOG_INFO, 
                amg_logger.LOG_USER, 
                G_LOGGER_STREAM)

    for key, value in globals().items():
        if (key.startswith("G_")):
            logger.info(f"{key} = {value}")


