#+----------------------------------------------------------+
#| The following parameters are encapsulated by this class: |
#|     (a) configuration                                    |
#|     (b) command line                                     |
#+----------------------------------------------------------+

import configparser
import sys
import os

import stt_default_config

class DefaultSttConfig ():

    # https://docs.python.org/3/library/configparser.html

    def __init__ (self):
        pass

    def get_config_parser (self):

        default_config = configparser.ConfigParser()
        default_config.read_string(stt_default_config.stt_default_config_str)
        return default_config

    def dump (self, file_obj=sys.stdout, with_comments=False):

        if (with_comments):
            print(stt_default_config.stt_default_config_str, file=file_obj)
        else:
            self.get_config_parser().write(file_obj)


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
    def_stt_config.dump ()

def utest2():

    def_stt_config = DefaultSttConfig ()
    def_stt_config.dump (sys.stderr, True)

def utest3():

    cp = generate_with_defaults (sys.argv[2], True)
    cp.write(sys.stdout)


if __name__ == '__main__':

    #https://stackoverflow.com/questions/3061/calling-a-function-of-a-module-by-using-its-name-a-string

    unit_test_fnx_name = "utest" + sys.argv[1] 
    locals()[unit_test_fnx_name]()

    #unit_test_fnx = getattr(__module__, unit_test_fnx_name)
    #unit_test_fnx = getattr("stt_config", unit_test_fnx_name)
    #unit_test_fnx()


