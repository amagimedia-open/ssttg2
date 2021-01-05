#+----------------------------------+
#| Command line argument processing |
#+----------------------------------+

import argparse
import configparser
import errno
import os
import io
import sys

import amg_logger
import stt_config

def set_default_cmdarg_values (cmdargs_parser):

    default_config = stt_config.DefaultSttConfig().get_config_parser()

    cmdargs_parser.add_argument(
            '-i', 
            '--input_audio_path', 
            default=default_config.get("FILES", "input_audio_path"),
            help="overrides ini->[FILES]/input_audio_path")

    cmdargs_parser.add_argument(
            '-o', 
            '--output_srt_path', 
            default=default_config.get("FILES", "output_srt_path"),
            help="overrides ini->[FILES]/output_srt_path")

    cmdargs_parser.add_argument(
            '-a', 
            '--gcp_auth_path',
            default=default_config.get("FILES", "gcp_auth_path"),
            help="overrides ini->[FILES]/gcp_auth_path")

    cmdargs_parser.add_argument(
            '-L', 
            '--logger_stream', 
            default=default_config.get("LOGGING", "logger_stream"),
            help="overrides ini->[LOGGING]/logger_stream")

    cmdargs_parser.add_argument(
            '-v', 
            '--verbose', action="store_true",
            default=default_config.getboolean("LOGGING", "verbose"),
            help="overrides ini->[LOGGING]/verbose")

    cmdargs_parser.add_argument(
            '-n', 
            '--no_run', 
            action="store_true",
            default=default_config.getboolean("OTHERS", "no_run"),
            help="overrides ini->[OTHERS]/no_run")

    return cmdargs_parser


def dump_cmdarg_values (cmdargs, logger):

    logger.info(f"cmdargs: input_audio_path = {cmdargs.input_audio_path}")
    logger.info(f"cmdargs: output_srt_path  = {cmdargs.output_srt_path}")
    logger.info(f"cmdargs: gcp_auth_path    = {cmdargs.gcp_auth_path}")
    logger.info(f"cmdargs: logger_stream    = {cmdargs.logger_stream}")
    logger.info(f"cmdargs: verbose          = {cmdargs.verbose}")
    logger.info(f"cmdargs: no_run           = {cmdargs.no_run}")


def set_cmdarg_values_in_config (config_parser, cmdargs):

    config_parser.set("FILES",   "input_audio_path", cmdargs.input_audio_path)
    config_parser.set("FILES",   "output_srt_path",  cmdargs.output_srt_path)
    config_parser.set("FILES",   "gcp_auth_path",    cmdargs.gcp_auth_path)
    config_parser.set("LOGGING", "logger_stream",    cmdargs.logger_stream)
    config_parser.set("LOGGING", "verbose",          str(cmdargs.verbose))
    config_parser.set("OTHERS",  "no_run",           str(cmdargs.no_run))


def gen_config_from_cmdargs (argv):
    """
        returns a ConfigParser object and contains the configuration
        (default/specified) overriden with command line arguments
    """

    cmdargs_parser = argparse.ArgumentParser ()

    #+--------------------------------------------------+
    #| Step 1: populate the argument parser with values |
    #|         from default configuration               |
    #+--------------------------------------------------+

    # use default configuration parser to set default cmdarg values
    set_default_cmdarg_values (cmdargs_parser)

    # -c is not part of the configuration
    cmdargs_parser.add_argument('-c', '--config_path', default="")

    #+--------------------------------------+
    #| Step 2: parse command line arguments |
    #+--------------------------------------+

    cmdargs = cmdargs_parser.parse_args (argv)

    #+---------------------------------------------+
    #| Step 3: Setup logger and dump cmdarg values |
    #+---------------------------------------------+

    # see stt_globals.py
    cmdargs_logger = amg_logger.amagi_logger (
                          "com.amagi.stt.cmdargs", 
                          amg_logger.LOG_INFO, 
                          log_stream=cmdargs.logger_stream)


    if (cmdargs.verbose):
        dump_cmdarg_values (cmdargs, cmdargs_logger)

    #+-----------------------------------------------+
    #| Step 4: create the desired configuration with |
    #|         command line overrides                |
    #+-----------------------------------------------+

    cp = None

    if (len(cmdargs.config_path) > 0):
        if (not os.path.isfile (cmdargs.config_path)):
            cmdargs_logger.error(f"configuration file {cmdargs.config_path} not found")
            raise FileNotFoundError(
                    errno.ENOENT, \
                    os.strerror(errno.ENOENT), \
                    cmdargs.config_path)

        # read the configuration with defaults supplied from
        # default configuration
        cp = stt_config.generate_with_defaults (cmdargs.config_path, cmdargs.verbose)

        if (cmdargs.verbose):
            cmdargs_logger.info(f"generated config from {cmdargs.config_path} with defaults")

    else:

        # use the default configuration
        cp = stt_config.DefaultSttConfig().get_config_parser()

        if (cmdargs.verbose):
            cmdargs_logger.info(f"generated default config")

    # override the configuration values with those specified
    # in command line
    set_cmdarg_values_in_config (cp, cmdargs)

    if (cmdargs.verbose):
        cmdargs_logger.info(f"config overwritten with cmdargs")

    # dump configuration using logger
    if (cmdargs.verbose):
        f_str = io.StringIO()
        cp.write(f_str)
        f_str.seek(0)
        cmdargs_logger.info(f_str.read())
        f_str.close()

    return cp


#+------------+
#| UNIT TESTS |
#+------------+

def utest1():
    """
        No arguments except --verbose
        (default configuration)
    """

    argv = ["--verbose"] 
    cp = gen_config_from_cmdargs (argv)

    # Note that configuration is dumped in gen_config_from_cmdargs 
    # on stderr (by default) if --verbose is set

def utest2():
    """
        Some arguments
        (default configuration)
    """

    argv = ["--verbose",
            "--input_audio_path", "in.pcm",
            "--output_srt_path",  "out.srt",
            "--gcp_auth_path",    "/foo/boo/auth.json",
            "--no_run"]

    cp = gen_config_from_cmdargs (argv)

    # Note that configuration is dumped in gen_config_from_cmdargs 
    # on stderr (by default) if --verbose is set

def utest3():
    """
        Some arguments
        Specified configuration
    """

    argv = ["--verbose",
            "--input_audio_path", "in.pcm",
            "--output_srt_path",  "out.srt",
            "--gcp_auth_path",    "/foo/boo/auth.json",
            "--no_run",
            "--config_path",      sys.argv[2]]

    cp = gen_config_from_cmdargs (argv)

    # Note that configuration is dumped in gen_config_from_cmdargs 
    # on stderr (by default) if --verbose is set

if __name__ == '__main__':

    unit_test_fnx_name = "utest" + sys.argv[1] 
    locals()[unit_test_fnx_name]()

