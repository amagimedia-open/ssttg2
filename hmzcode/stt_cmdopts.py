#+----------------------------------+
#| Command line argument processing |
#+----------------------------------+

import argparse
import configparser
import stt_config

def set_default_cmdopt_values (cmdopts_parser):

    default_config = stt_config.DefaultSttConfig().get_config_parser()

    cmdopts_parser.add_argument(
            '-i', 
            '--input_audio_path', 
            default=default_config.get("FILES", "input_audio_path"),
            help="overrides ini->[FILES]/input_audio_path")

    cmdopts_parser.add_argument(
            '-o', 
            '--output_srt_path', 
            default=default_config.get("FILES", "output_srt_path"),
            help="overrides ini->[FILES]/output_srt_path")

    cmdopts_parser.add_argument(
            '-a', 
            '--gcp_auth_path', default="",
            default=default_config.get("FILES", "gcp_auth_path"),
            help="overrides ini->[FILES]/gcp_auth_path")

    cmdopts_parser.add_argument(
            '-L', 
            '--logger_stream', 
            default=default_config.get("LOGGING", "logger_stream"),
            help="overrides ini->[LOGGING]/logger_stream")

    cmdopts_parser.add_argument(
            '-v', 
            '--verbose', action="store_true",
            default=default_config.get("LOGGING", "verbose"),
            help="overrides ini->[LOGGING]/verbose")

    cmdopts_parser.add_argument(
            '-n', 
            '--norun', 
            action="store_true",
            default=default_config.get("OTHERS", "no_run"),
            help="overrides ini->[OTHERS]/no_run")

    return cmdopts_parser


def dump_cmdopt_values (args):

    main_logger.info(f"cmdopts: input_audio_path = {args.input_audio_path}")
    main_logger.info(f"cmdopts: output_srt_path  = {args.output_srt_path}")
    main_logger.info(f"cmdopts: gcp_auth_path    = {args.gcp_auth_path}")
    main_logger.info(f"cmdopts: logger_stream    = {args.logger_stream}")
    main_logger.info(f"cmdopts: verbose          = {args.verbose}")
    main_logger.info(f"cmdopts: no_run           = {args.no_run}")


def set_cmdopt_values_in_config (config_parser, args, verbose=False):

    opt_verbose     = args.verbose
    opt_no_run      = args.norun

    config_parser.set("FILES",   "input_audio_path", args.input_audio_path)
    config_parser.set("FILES",   "output_srt_path",  args.output_srt_path)
    config_parser.set("FILES",   "gcp_auth_path",    args.gcp_auth_path)
    config_parser.set("LOGGING", "logger_stream",    args.logger_stream)
    config_parser.set("LOGGING", "verbose",          args.verbose)
    config_parser.set("OTHERS",  "no_run",           args.no_run)


def handle_cmdopts (verbose=False):

    parser = argparse.ArgumentParser ()

    # use default configuration parser to set default cmdopt values
    set_default_cmdopt_values (parser)

    # -c is not part of the configuration
    parser.add_argument('-c', '--conf', default="", required=True)

    args = parser.parse_args ()

    # set up the logger (soonest possible is here)
    # see stt_globals.py
    main_logger = amg_logger.amagi_logger (
                  "com.amagi.stt.main", 
                  amg_logger.LOG_INFO, 
                  log_stream=args.logger_stream)

    dump_cmdopt_values (args)

    if (not os.path.isfile (args.conf)):
        main_logger.error(f"configuration file {args.conf} not found")
        return False

    # read the configuration where defaults for keys that are
    # not supplied are got from the default configuration
    cp = stt_config.generate_with_defaults (args.conf, verbose)

    # override the configuration values with those specified
    # in command line
    set_cmdopt_values_in_config (cp, args, verbose)


