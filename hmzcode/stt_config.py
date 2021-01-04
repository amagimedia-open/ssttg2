#+----------------------------------------------------------+
#| The following parameters are encapsulated by this class: |
#|     (a) configuration                                    |
#|     (b) command line                                     |
#+----------------------------------------------------------+

import configparser
import sys
import os

class DefaultSttConfig ():

    # https://docs.python.org/3/library/configparser.html

    def __init__ (self):

        self.default_config_str = """
[FILES]

input_audio_path = /dev/stdin

    # the input wav file path encoded as pcm_s16le at 16000 Hz

output_srt_path = /dev/stdout

    # the output srt file path

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

#-------------------------------------------------------------------

[LOGGING]

verbose=false

    # verboseness needed for debugging. values are true|false.

logger_stream=stderr

    # values are stderr|syslog

#-------------------------------------------------------------------

[OTHERS]

no_run=false

    # does not run the program. useful to check configuration.
    # values are true|false
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


def gen_with_defaults (filepath, verbose=False):
    """
    reads the configuration file and supplied default values 
    from DefaultSttConfig
    returns a ConfigParser object
    """

    default_config = DefaultSttConfig().get_config_parser()

    input_config = configparser.ConfigParser()
    input_config.read(filepath)

    gen_config = configparser.ConfigParser()

    for section in default_config.sections():
        for (key, val) in default_config.items(section):

            set_default_value = False

            try:
                val = input_config.get(section, key)
                if (verbose):
                    print(f"val=infile,  file={filepath}, section={section}, key={key}, value={val}")

            except configparser.NoSectionError:
                set_default_value = True

            except configparser.NoOptionError:
                set_default_value = True

            if (set_default_value):
                if (verbose):
                    print(f"val=default, file={filepath}, section={section}, key={key}, value={val}")

            if (not gen_config.has_section(section)):
                gen_config.add_section(section)

            gen_config.set(section, key, val)

    return gen_config


def utest1():

    def_stt_config = DefaultSttConfig ()
    def_stt_config.dump2stdout (False)


def utest2():

    cp = gen_with_defaults (sys.argv[2], True)
    cp.write(sys.stdout)


if __name__ == '__main__':

    #https://stackoverflow.com/questions/3061/calling-a-function-of-a-module-by-using-its-name-a-string

    unit_test_fnx_name = "utest" + sys.argv[1] 
    locals()[unit_test_fnx_name]()

    #unit_test_fnx = getattr(__module__, unit_test_fnx_name)
    #unit_test_fnx = getattr("stt_config", unit_test_fnx_name)
    #unit_test_fnx()


