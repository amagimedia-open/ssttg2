#!/bin/bash

set -u
set -x

#----[globals]------------------------------------------------------------------------

DIRNAME=$(dirname $(readlink -e $0))
MODNAME=$(basename $0)

mkdir -p $DIRNAME/testdata

#        -v $DIRNAME/testdata:/data \

docker run \
        -it \
        --rm \
        --privileged \
        --network host \
        --name ssttg_dev_c \
        -v $DIRNAME:/ssttg \
        -e SSTTG_DEV_ROOT=/ssttg \
        -e TEST_SOURCE_FILE_PATH=/ssttg/sstt_testclip_20_sec.mp4 \
        -w /ssttg \
        ssttg_dev \
        /ssttg/run_ut.sh

# in docker do the following
# ./test/in/runall.sh
