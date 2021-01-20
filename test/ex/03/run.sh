#!/bin/bash

set -u
set -e
set -x

#----[options]------------------------------------------------------------------------

#OPT_DURATION="00:00:00"
OPT_CREATE_SILENCE=0
#OPT_DURATION="00:10:00"
OPT_TEST_WITH_FFPLAY=0
OPT_ADD_SILENCE_SEC=0

#----[globals]------------------------------------------------------------------------

DIRNAME=$(dirname $(readlink -e $0))
MODNAME=$(basename $0)
DATADIR=$DIRNAME/testdata
#TEST_CLIP_FILE_PATH=$(readlink -e $DIRNAME/../../../sstt_testclip_20_sec.mp4)
TEST_CLIP_FILE_PATH=$(readlink -e $DIRNAME/../../../curiosity.aac)
AUTH_JSON_FILE_PATH=$(readlink -e ~/aimlapis-34d0d055c12d.json)

#----[temp files and termination]--------------------------------------------

function fnxOnEnd
{
    rm $TMP1 $TMP2
    [[ -t 0 ]] && { stty sane; }
}

TMP1=`mktemp`
TMP2=`mktemp`

trap 'fnxOnEnd;' 0 1 2 3 6 9 11

#----[main]------------------------------------------------------------------

mkdir -p $DATADIR
rm -vf $DATADIR/*

cp $TEST_CLIP_FILE_PATH $DATADIR
cp $AUTH_JSON_FILE_PATH $DATADIR/auth.json

#-----------------------------------------------------

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

#-----------------------------------------------------

(
    #-i anullsrc=r=16000:cl=mono     \

    if ((OPT_CREATE_SILENCE))
    then
        #https://gist.github.com/daz/30862fdd0fef80c1bbed37204c9d8a14
        ffmpeg                              \
            -loglevel quiet                 \
            -re                             \
            -f lavfi                        \
            -i anullsrc=r=16000             \
            -t $OPT_DURATION                \
            -acodec pcm_s16le -ac 1 -ar 16k \
            -f s16le                        \
            pipe:1
    else
        ffmpeg                              \
            -loglevel quiet                 \
            -re                             \
            -i $TEST_CLIP_FILE_PATH         \
            $FFMPEG_ADD_SILENCE_OPTS        \
            $FFMPEG_DURATION_OPT            \
            -vn                             \
            -acodec pcm_s16le -ac 1 -ar 16k \
            -f s16le                        \
            pipe:1
    fi
) |\
(
    if ((OPT_TEST_WITH_FFPLAY))
    then
        ffplay -autoexit -f s16le -ar 16k -
    else    
        #https://stackoverflow.com/a/43099210/1029379
        docker run \
            -i \
            --rm \
            --privileged \
            --network host \
            --name ssttg2_rel_c \
            -v $DATADIR:/data \
            ssttg2_rel \
            /ssttg/ssttg.sh \
                -O transcribepcm \
                -v \
                -o /data/out.srt \
                -d /data/out_dbg.txt \
                -a /data/auth.json
    fi
)

stty sane
