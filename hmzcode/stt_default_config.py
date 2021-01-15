#+---------------------------+
#| The default configuration |
#+---------------------------+

stt_default_config_str = """

#
#  Thu Jan  7 13:31:48 IST 2021
#
#  +--------------------------+
#  | streaming speech to text |
#  |     configuration        |
#  +--------------------------+
#
#  +-----------------------------------+   --+
#  |default configuration              |     |
#  |(base)                             |     |
#  |  +----------------------------+   |     |
#  |  | specific configuration     |   |     |
#  |  | (override 1)               |   |     |final
#  |  | (-c)                       |   |     |configuration
#  |  | (optional)                 |   |     |
#  |  |   +----------------------+ |   |     |
#  |  |   | command line options | |   |     |
#  |  |   | (override 2)         | |   |     |
#  |  |   | (-i,-o, ...)         | |   |     |
#  |  |   | (optional)           | |   |     | 
#  |  |   +----------------------+ |   |     |
#  |  +----------------------------+   |     |
#  +-----------------------------------+   --+
#

[FILES]

input_audio_path = /dev/stdin

    # the input wav file path encoded as pcm_s16le at 16000 Hz
    # this by default is stdin. it could also be the path to a
    # named pipe.
    # can override with : -i option

output_srt_path = /dev/stdout

    # the output srt file path
    # can override with : -o option

phrases_path = /mnt/ops/livetranscription/phrases_path

    # the phrases file path needed by gcp speech-to-text api
    # can override with : -p option

gcp_auth_path = /mnt/ops/livetranscription/auth.json

    # the auth file path in json format needed by gcp 
    # speech-to-text api
    # can override with : -a option


#-------------------------------------------------------------------

[TRANSLATION]

min_word_drain_delay_sec = 3.0

    # When to drain words from the accumulated list.
    # time diff b/w word_time_offsets.

max_inter_word_duration_ms = 800

    # Maximum allowed word_time_off between two words.
    # If diff is more next word is put in new subtitle line.

max_subtitle_line_duration_ms = 1500

    # Max duration of a subtitle line

max_chars_in_sub_row = 30

    # Maximum characters in a subtitle line.

max_words_to_search = 4

    # When a new word is inserted between two existing words,
    # how far do we need to go and search.

#-------------------------------------------------------------------

[IFLAGS]                        
    # input flags

exit_on_zero_size=true

    # If true, terminates the streamin_stt program upon 
    # reception of a packet with size 0
    # See the -z option in stt_audio_packetizer

last_log_time_quanta_ms=5

    # see ReadGen.run

#-------------------------------------------------------------------

[OFLAGS]
    # output flags

append_mode=true

    # If true, opens the output (srt) file in append mode. 
    # default is write (overwrite) mode.

append_null_char=false

    # If true, appends the ascii null char after each 
    # line of srt output

#-------------------------------------------------------------------

[LOGGING]

verbose=false

    # verboseness needed for debugging. values are true|false.
    # can override with : -v option


logger_stream=stderr

    # values are stderr|syslog
    # can override with : -L option

#-------------------------------------------------------------------

[OTHERS]

no_run=false

    # does not run the program. useful to check configuration.
    # values are true|false
    # can override with : -n option
"""

