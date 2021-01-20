#!/bin/bash

set -u
set -e
set -x

#----[options]------------------------------------------------------------------------

#OPT_DURATION="00:00:20"
OPT_DURATION=""
OPT_ADD_SILENCE_SEC=2

#----[globals]------------------------------------------------------------------------

DIRNAME=$(dirname $(readlink -e $0))
MODNAME=$(basename $0)

TEST_CLIP_FILE_PATH=$(readlink -e $DIRNAME/../curiosity.aac)
AUTH_JSON_FILE_PATH=$(readlink -e $DIRNAME/../auth.json)

#----[temp files and termination]--------------------------------------------

function fnxOnEnd
{
    if ((TERMINATED==0))
    then
        rm -vf $TMP1 $TMP2
        [[ -t 0 ]] && { stty sane; }
        TERMINATED=1
    fi
}

TERMINATED=0
TMP1=`mktemp`
TMP2=`mktemp`

trap 'fnxOnEnd;' 0 1 2 3 6 9 11

#----[main]---------------------------------------------------------------------------

if [[ ! -f $TEST_CLIP_FILE_PATH ]]
then
    echo "$TEST_CLIP_FILE_PATH not present" >&2
    exit 1
fi

if [[ ! -f $AUTH_JSON_FILE_PATH ]]
then
    echo "$AUTH_JSON_FILE_PATH not present" >&2
    exit 1
fi

mkdir -p $DIRNAME/t_data
rm -vf $DIRNAME/t_data/*

FFMPEG_DURATION_OPT=""
if [[ -n ${OPT_DURATION-""} ]] 
then
    FFMPEG_DURATION_OPT=" -t ${OPT_DURATION} "
fi

FFMPEG_ADD_SILENCE_OPTS=""
if ((OPT_ADD_SILENCE_SEC > 0))
then
    #https://superuser.com/a/579110
    FFMPEG_ADD_SILENCE_OPTS="
        -f lavfi 
        -t $OPT_ADD_SILENCE_SEC 
        -i anullsrc=r=16000 
        -filter_complex [0:a][1:a]concat=n=2:v=0:a=1"
fi

(
    set -u
    set -e
    set -x

    ffmpeg                              \
        -loglevel quiet                 \
        -re                             \
        -i $TEST_CLIP_FILE_PATH         \
        $FFMPEG_ADD_SILENCE_OPTS        \
        $FFMPEG_DURATION_OPT            \
        -vn                             \
        -acodec pcm_s16le -ac 1 -ar 16k \
        -f s16le                        \
        pipe:1                          \
    |\
    $DIRNAME/sstt_h_audio_packetizer    \
        -z                              \
    |\
    $DIRNAME/sstt_h_audio_depacketizer  \
        -vv                             \
        -z                              \
        -f                              \
    |\
    python3 $DIRNAME/streaming_stt.py \
        -v                              \
        -o $DIRNAME/t_data/t_run.srt    \
        -c $DIRNAME/stt_cfg.ini         \
        -a $AUTH_JSON_FILE_PATH         \
        -d $DIRNAME/t_data/t_gcp_response.txt
) 2>$DIRNAME/t_data/t_dbg.srt

stty sane
