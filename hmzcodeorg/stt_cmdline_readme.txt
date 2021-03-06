speech_to_text.py can be renamed to streaming_stt.py
Its usage can be as follows:

NAME

    streaming_stt.py - performs streaming speech to text transcription.


SYNOPSIS

    streaming_stt.py [-i packetized_audio_filepath] [-o srt_filepath] 
                     [-a auth_json_filepath] [-c config.ini] [-h]


DESCRIPTION

    The streamin_stt.py program performs a streaming transcription of
    a (packetized) wav file using the google speech to text api.

    The input (packetized wav) data must be supplied through the 
    stt_audio_packetizer program.

    The parameters/options/configuration for the transcription process 
    must be specified through an ini file (via the -c option) whose format 
    is as follows:

    #-------------------------------------------------------------------------

    [IFLAGS]                        # input flags

    exit_on_zero_size=true          # If true, the streamin_stt program 
                                    # upon reception of a packet with size 0
                                    # This is optional. Default is false.
                                    # See the -z option in stt_audio_packetizer

    last_log_time_quanta_ms=5       # optional. default is 5.
                                    # TODO: Hamza to add comments here
                                    # see ReadGen.run

    #-------------------------------------------------------------------------

    [OFLAGS]                        # output flags

    append_mode=true                # If true, opens the output file in 
                                    # append mode. 
                                    # This is optional. Default is false.
                                    # (implying opening of output file in
                                    #  write mode)

    append_null_char=true           # If true, appends the ascii null char
                                    # ('\0') after each line of srt output
                                    # This is optional. Default is false.

    #-------------------------------------------------------------------------

    [TRANSCRIPTION]                         # algorithmic parameters
                                            # TODO: Hamza to add comments for
                                            # all the names in this section

    timeout_seconds = 3                     # optional. default is 3

    repeat_sub_threashold_ms = 1000         # optional. default is 1000

    write_after_characters_recvd = 150      # optional. default is 150

    max_sub_chars = 30                      # optional. default is 30

    streaming_limit = 240000                # optional. default is 240000

    min_sub_duration_ms = 400               # optional. default is 400

    max_sub_duration_ms = 4000              # optional. default is 4000

    #------------------------------ EOF --------------------------------------


OPTIONS

    -i  packetized_audio_filepath

        The input packetized audio file (generated by stt_audio_packetizer).
        This is optional. Default is stdin.

    -o  srt_filepath

        The output srt file.
        This is optional. Default is stdout.

    -c  config.ini
        The name of the configuration file.
        The environment variable STREAMING_STT_CFG_FILEPATH is expected to
        be defined if this option is not specified.

    -a  auth.json
        The name of the authorization file to be used for invoking the google
        speech to text api.
        The environment variable GOOGLE_APPLICATION_CREDENTIALS is expected to
        be defined if this option is not specified.

    -h
        This help.
        This is optional.


EXAMPLES

    stt_audio_packetizer -i audio.wav -p 0 -z |\
    streaming_stt.py -c streaming_stt_config.ini -a auth.json -z > srt.txt


