#+----------------------------------------------------------+
#| The following parameters are encapsulated by this class: |
#|     (a) configuration                                    |
#|     (b) command line                                     |
#+----------------------------------------------------------+

import configparser
import sys

class DefaultSttConfig ():

    # https://docs.python.org/3/library/configparser.html

    def __init__ (self):

        self.default_config_str = """
[FILES]

gcp_auth_path = /mnt/ops/livetranscription/auth.json

    # the auth file path in json format needed by gcp 
    # speech-to-text api

phrases_path = /mnt/ops/livetranscription/phrases_path

    # the phrases file path needed by gcp speech-to-text api

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

append_null_char=true

    # If true, appends the ascii null char ('\0') after each 
    # line of srt output
"""

    def get_config_parser (self):

        default_config = configparser.ConfigParser()
        default_config.read_string(self.default_config_str)
        return default_config

    def dump2stdout (self, with_comments=True):

        if (with_comments):
            print(self.default_config_str)
        else:
            cp = self.get_config_parser ()
            cp.write(sys.stdout)

if __name__ == '__main__':

    def_stt_config = DefaultSttConfig ()
    def_stt_config.dump2stdout (False)

