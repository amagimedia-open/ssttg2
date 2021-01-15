#!/bin/bash

set -u
#set -x

#----[options]------------------------------------------------------------------------

OPT_DURATION=""
OPT_ADD_SILENCE_SEC=2
#TEST_SOURCE_FILE_PATH=$SSTTG_DEV_ROOT/curiosity_1c_16k_10m.aac
#TEST_SOURCE_FILE_PATH=$SSTTG_DEV_ROOT/curiosity.aac

#----[globals]------------------------------------------------------------------------

DIRNAME=$(dirname $(readlink -e $0))
MODNAME=$(basename $0)

#----[sources]---------------------------------------------------------------

source $SSTTG_DEV_ROOT/common_bash_functions.sh

#----[options]---------------------------------------------------------------

#----[temp files and termination]--------------------------------------------

function fnxOnEnd
{
    rm $TMP1 $TMP2
}

TMP1=`mktemp`
TMP2=`mktemp`

trap 'fnxOnEnd;' 0 1 2 3 6 9 11

#----[main]------------------------------------------------------------------

export PATH=$PATH:$SSTTG_DEV_ROOT

if [[ ${1-""} = "clean" ]]
then
    info_message "cleaning up ..."
    rm_other_than $TMP1 $DIRNAME run.sh out.srt.gold
    exit 0
fi

if [[ ! -f $TEST_SOURCE_FILE_PATH ]]
then
    error_message "$TEST_SOURCE_FILE_PATH not present"
    exit 2
fi

if [[ ! -f $SSTTG_DEV_ROOT/auth.json ]]
then
    error_message "$SSTTG_DEV_ROOT/auth.json not present"
    exit 2
fi

rm -f $DIRNAME/out.srt $DIRNAME/out_dbg.txt

#set -x

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

ffmpeg \
    -loglevel quiet \
    -re \
    -i $TEST_SOURCE_FILE_PATH \
    $FFMPEG_ADD_SILENCE_OPTS \
    $OPT_DURATION \
    -acodec pcm_s16le -ac 1 -ar 16k \
    -f s16le \
    pipe:1 \
|\
ssttg.sh \
    -O transcribepcm \
    -v \
    -o $DIRNAME/out.srt \
    -d $DIRNAME/out_dbg.txt \
    -a $SSTTG_DEV_ROOT/auth.json \
    -p ""

    #-t

stty sane

if ! diff $DIRNAME/out.srt $DIRNAME/out.srt.gold
then
    error_message "failed"
    exit 2
fi

info_message "passed"
exit 0

#set +x

