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
import stt_commons
import stt_globals

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

    #+-----------------------------------------------+
    #| Step 2: create the desired configuration with |
    #|         command line overrides                |
    #+-----------------------------------------------+

    cp = None

    if (len(cmdargs.config_path) > 0):
        if (not os.path.isfile (cmdargs.config_path)):
            stt_commons.eprint(f"configuration file {cmdargs.config_path} not found")
            raise FileNotFoundError(
                    errno.ENOENT, \
                    os.strerror(errno.ENOENT), \
                    cmdargs.config_path)

        # read the configuration with defaults supplied from
        # default configuration
        cp = stt_config.generate_with_defaults (cmdargs.config_path, cmdargs.verbose)

        if (cmdargs.verbose):
            stt_commons.eprint(f"generated config from {cmdargs.config_path} with defaults")

    else:

        # use the default configuration
        cp = stt_config.DefaultSttConfig().get_config_parser()

        if (cmdargs.verbose):
            stt_commons.eprint(f"generated default config")

    #+----------------------------------------------------------------+
    #| Step 4: override the configuration values with those specified |
    #|         in command line and dump final configuration           |
    #+----------------------------------------------------------------+

    set_cmdarg_values_in_config (cp, cmdargs)

    logger = amg_logger.amagi_logger (
                "com.amagi.stt.cmdargs", 
                amg_logger.LOG_INFO, 
                amg_logger.LOG_USER, 
                cp.get("LOGGING", "logger_stream"))

    if (cp.getboolean("LOGGING", "verbose")):
        dump_cmdarg_values (cmdargs, logger)

    if (cp.getboolean("LOGGING", "verbose")):
        logger.info(f"final configuration is as follows:")
        f_str = io.StringIO()
        cp.write(f_str)
        f_str.seek(0)
        logger.info(f_str.read())
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
            "-i",                 "in.pcm",
            "-o",                 "out.srt",
            "--gcp_auth_path",    "/foo/boo/auth.json",
            "--no_run",
            "--config_path",      sys.argv[2]]

    cp = gen_config_from_cmdargs (argv)


def utest4():
    """
        Some arguments
        Specified configuration
        Set globals using configuration
    """

    argv = ["--verbose",
            "--input_audio_path", "in.pcm",
            "--output_srt_path",  "out.srt",
            "--gcp_auth_path",    "/foo/boo/auth.json",
            "--config_path",      sys.argv[2]]

    cp = gen_config_from_cmdargs (argv)
    stt_globals.config_2_globals(cp)
    stt_globals.dump_globals()


if __name__ == '__main__':

    unit_test_fnx_name = "utest" + sys.argv[1] 
    locals()[unit_test_fnx_name]()

