#+----------------------------------------------------------+
#| The following parameters are encapsulated by this class: |
#|     (a) configuration                                    |
#|     (b) command line                                     |
#+----------------------------------------------------------+

import configparser
import sys
import os

import stt_default_config
import stt_commons

class DefaultSttConfig ():

    # https://docs.python.org/3/library/configparser.html

    def __init__ (self):
        pass

    def get_config_parser (self):

        default_config = configparser.ConfigParser()
        default_config.read_string(stt_default_config.stt_default_config_str)
        return default_config

    def dump (self, with_comments=False):

        if (with_comments):
            stt_commons.eprint(stt_default_config.stt_default_config_str)
        else:
            self.get_config_parser().write(sys.stderr)


def generate_with_defaults (filepath, verbose=False):
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
                    stt_commons.eprint(f"val=infile,  file={filepath}, section={section}, key={key}, value={val}")

            except configparser.NoSectionError:
                set_default_value = True

            except configparser.NoOptionError:
                set_default_value = True

            if (set_default_value):
                if (verbose):
                    stt_commons.eprint(f"val=default, file={filepath}, section={section}, key={key}, value={val}")

            if (not gen_config.has_section(section)):
                gen_config.add_section(section)

            gen_config.set(section, key, val)

    return gen_config

#+------------+
#| UNIT TESTS |
#+------------+

def utest1():

    def_stt_config = DefaultSttConfig ()
    def_stt_config.dump ()

def utest2():

    def_stt_config = DefaultSttConfig ()
    def_stt_config.dump (True)

def utest3():

    cp = generate_with_defaults (sys.argv[2], True)
    cp.write(sys.stderr)


if __name__ == '__main__':

    unit_test_fnx_name = "utest" + sys.argv[1] 
    locals()[unit_test_fnx_name]()

