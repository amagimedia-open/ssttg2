pipe_write can be renamed to stt_audio_packetizer
Its usage can be as follows:

NAME
    stt_audio_packetizer - packetizes wav data for consumption by 
                           streaming_stt.py


SYNOPSIS

    stt_audio_packetizer [-i audio.wav] [-o packetized_audio]
                         [-p start_ts] [-s sleep_bw_packets_us]
                         [-z] [-h]


DESCRIPTION

    The stt_audio_packetizer reads a wav file and creates packets on the 
    output. Each packet is composed of a 14 byte header and data from the
    wav file.
    This filter reads from stdin and writes to stdout by default.

    The composition of a packet is as follows:

    header
        signature       4 bytes     (fixed to 0xc0, 0xff, 0xee, 0xee)
        ts              8 bytes     (variable time stamp)
        size            2 bytes     (fixed to 32 * 16 * 2)
    data
        'size' amount of bytes read from the input wav file

    The fixed chunk 'size' is derived as follows:

    16Khz => 16000 samples/sec
    2 bytes per sample => (16000 * 2) samples/sec
    Samples per millisec = ((16000 * 2)/1000)
    Samples for 32 millisec = (32*(16000*2)/1000) = 32 * 16 * 2

    The input wav file must be in the format as expressed by the 
    following command:

    ffmpeg -i {input.ts|wav|mp4} \
           -vn -acodec pcm_s16le -ac 1 -ar 16k audio.wav

    that is pcm in 16kHz, Mono, 2 bytes per sample, little endian format.


OPTIONS

    -i  audio.wav
        The name of the wav file. 
        This is optional. Default is stdin.

    -o  packetized_audio
        The name of the output file. 
        This is optional. Default is stdout.

    -p  start_ts
        The starting timestamp value.
        This is optional. Default is (2^63)/1000000.

    -s  sleep_bw_packets_us
        sleep duration between packets in microseconds.
        This is optional. Default is 10000.

    -z  
        End of input signalled via a size of 0 in the packet header.
        This is optional.

    -h
        This help.
        This is optional.


EXAMPLES

    stt_audio_packetizer -i audio.wav -p 0 -z 

