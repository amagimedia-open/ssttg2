#!/bin/bash

set -u
set -e
set -x

#----[globals]------------------------------------------------------------------------

DIRNAME=$(dirname $(readlink -e $0))
MODNAME=$(basename $0)
DATADIR=$DIRNAME/testdata
TEST_CLIP_FILE_PATH=$(readlink -e $DIRNAME/../../../sstt_testclip_20_sec.mp4)
AUTH_JSON_FILE_PATH=$(readlink -e $DIRNAME/../../../auth.json)

mkdir -p $DATADIR

rm -f $DATADIR/*

cp $TEST_CLIP_FILE_PATH $DATADIR
cp $AUTH_JSON_FILE_PATH $DATADIR

docker run \
        --rm \
        --privileged \
        --network host \
        --name ssttg2_rel_c \
        -v $DATADIR:/data \
        ssttg2_rel \
        /ssttg/ssttg.sh \
            -v \
            -s 2 \
            -i /data/sstt_testclip_20_sec.mp4 \
            -o /data/out.srt \
            -d /data/out_dbg.txt \
            -a /data/auth.json


