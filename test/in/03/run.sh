#!/bin/bash

set -u
#set -x

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

set -x

# -x \
ssttg.sh \
    -O transcribe \
    -x \
    -v \
    -t \
    -s 5 \
    -i $TEST_SOURCE_FILE_PATH \
    -o $DIRNAME/out.srt \
    -d $DIRNAME/out_dbg.txt \
    -a $SSTTG_DEV_ROOT/auth.json \
    -p ""

set +x


#if ! diff $DIRNAME/out.srt $DIRNAME/out.srt.gold >/dev/null 2>&1
#then
#    error_message "output differing from $DIRNAME/out.srt.gold"
#    exit 2
#fi

