#!/bin/bash

set -u
#set -x

#----[globals]------------------------------------------------------------------------

DIRNAME=$(readlink -e $(dirname $0))
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
    rm_other_than $TMP1 $DIRNAME run.sh test_cfg.ini out.gold
    exit 0
fi

set -x

(
    python3 $SSTTG_DEV_ROOT/hmzcode/stt_config_fnxs.py 1 
    python3 $SSTTG_DEV_ROOT/hmzcode/stt_config_fnxs.py 2 
    python3 $SSTTG_DEV_ROOT/hmzcode/stt_config_fnxs.py 3 $DIRNAME/test_cfg.ini
) 1>$TMP1 2>&1

set +x

cat $TMP1 > $DIRNAME/out.txt

if ! diff $TMP1 $DIRNAME/out.gold
then
    error_message "failed"
    exit 2
fi

info_message "passed"
exit 0

