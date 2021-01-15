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
DATADIR=$DIRNAME/testdata
TEST_CLIP_FILE_PATH=$(readlink -e $DIRNAME/../../../sstt_testclip_20_sec.mp4)
AUTH_JSON_FILE_PATH=$(readlink -e $DIRNAME/../../../auth.json)

mkdir -p $DATADIR

rm -vf $DATADIR/*

cp $TEST_CLIP_FILE_PATH $DATADIR
cp $AUTH_JSON_FILE_PATH $DATADIR

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

# https://stackoverflow.com/a/43099210/1029379

ffmpeg \
    -loglevel quiet \
    -re \
    -i $TEST_CLIP_FILE_PATH \
    $FFMPEG_ADD_SILENCE_OPTS \
    $OPT_DURATION \
    -vn \
    -acodec pcm_s16le -ac 1 -ar 16k \
    -f s16le \
    pipe:1 \
|\
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

stty sane
