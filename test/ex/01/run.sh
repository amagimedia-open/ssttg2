#!/bin/bash

set -u
#set -x

#----[globals]------------------------------------------------------------------------

DIRNAME=$(dirname $(readlink -e $0))
MODNAME=$(basename $0)

mkdir -p $DIRNAME/testdata

#        -it \

docker run \
        --rm \
        --privileged \
        --network host \
        --name ssttg2_rel_c \
        -v $DIRNAME/testdata:/data \
        ssttg2_rel \
        /ssttg/ssttg.sh -h

