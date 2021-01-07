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
import stt_default_config

def set_default_cmdarg_values (cmdargs_parser):

    default_config = stt_config.DefaultSttConfig().get_config_parser()

    # -c, -C is not part of the configuration

    cmdargs_parser.add_argument(
            '-C', 
            '--dump_def_config', 
            action="store_true",
            default=False,
            help="dump the default configuration file to stderr and exit")

    cmdargs_parser.add_argument(
            '-c', 
            '--config_path', 
            default="",
            help="specifies the path to the configuration file to be used")

    # config file overrideables

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
            '-p', 
            '--phrases_path', 
            default=default_config.get("FILES", "phrases_path"),
            help="overrides ini->[FILES]/phrases_path")

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
            '--verbose', 
            action="store_true",
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
    logger.info(f"cmdargs: phrases_path     = {cmdargs.phrases_path}")
    logger.info(f"cmdargs: gcp_auth_path    = {cmdargs.gcp_auth_path}")
    logger.info(f"cmdargs: logger_stream    = {cmdargs.logger_stream}")
    logger.info(f"cmdargs: verbose          = {cmdargs.verbose}")
    logger.info(f"cmdargs: no_run           = {cmdargs.no_run}")


def set_cmdarg_values_in_config (config_parser, cmdargs):

    config_parser.set("FILES",   "input_audio_path", cmdargs.input_audio_path)
    config_parser.set("FILES",   "output_srt_path",  cmdargs.output_srt_path)
    config_parser.set("FILES",   "phrases_path",     cmdargs.phrases_path)
    config_parser.set("FILES",   "gcp_auth_path",    cmdargs.gcp_auth_path)
    config_parser.set("LOGGING", "logger_stream",    cmdargs.logger_stream)
    config_parser.set("LOGGING", "verbose",          str(cmdargs.verbose))
    config_parser.set("OTHERS",  "no_run",           str(cmdargs.no_run))


def gen_config_from_cmdargs (argv):
    """
        returns either (dump_def_config=True,  ConfigParser=None)
                or     (dump_def_config=False, ConfigParser=...)

        the ConfigParser object contains 
            * the default configuration
            * overridden by the optional specified configuration and 
            * finally overridden by the optional command line arguments

        the expected behaviour of the caller should be as follows:

        if (dump_def_config == true):
            # dump default config on stderr
            # exit

        use the ConfigParser object to run the program
    """

    cmdargs_parser = argparse.ArgumentParser ()

    #+--------------------------------------------------+
    #| Step 1: populate the argument parser with values |
    #|         from default configuration               |
    #+--------------------------------------------------+

    # use default configuration parser to set default cmdarg values
    set_default_cmdarg_values (cmdargs_parser)

    #+--------------------------------------+
    #| Step 2: parse command line arguments |
    #+--------------------------------------+

    cmdargs = cmdargs_parser.parse_args (argv)

    if (cmdargs.dump_def_config):
        return (True, None)

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
            stt_commons.eprint(f"using config from {cmdargs.config_path} with defaults")

    else:

        # use the default configuration
        cp = stt_config.DefaultSttConfig().get_config_parser()

        if (cmdargs.verbose):
            stt_commons.eprint(f"using default config")

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

    return (False, cp)


#+------------+
#| UNIT TESTS |
#+------------+

def utest1():
    """
        No arguments except --verbose
        (default configuration)
    """

    argv = ["--verbose"] 
    (dump_def_config, cp) = gen_config_from_cmdargs (argv)

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

    (dump_def_config, cp) = gen_config_from_cmdargs (argv)

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

    (dump_def_config, cp) = gen_config_from_cmdargs (argv)


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

    (dump_def_config, cp) = gen_config_from_cmdargs (argv)
    stt_globals.config_2_globals(cp)
    stt_globals.dump_globals()

def utest5():
    """
        invocation of the implicit help option/argument
    """

    argv = ["--help"]

    (dump_def_config, cp) = gen_config_from_cmdargs (argv)

def utest6():
    """
        dump default configuration 
    """

    argv = ["-C",
            "-i", "in.pcm",
            "-o", "out.srt"]

    (dump_def_config, cp) = gen_config_from_cmdargs (argv)
    if (dump_def_config):
        print(stt_default_config.stt_default_config_str, file=sys.stderr)

if __name__ == '__main__':

    unit_test_fnx_name = "utest" + sys.argv[1] 
    locals()[unit_test_fnx_name]()

