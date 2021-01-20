#!/bin/bash

set -u
#set -x

#----[options]------------------------------------------------------------------------

#----[globals]------------------------------------------------------------------------

DIRNAME=$(dirname $(readlink -e $0))
MODNAME=$(basename $0)

TEST_DEBUG_FILE_PATH=$(readlink -e $DIRNAME/../../ex/03/testdata/out_dbg.txt)
SSTTG_DEV_ROOT=$(readlink -e ../../..)

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

if [[ ${1-""} = "clean" ]]
then
    info_message "cleaning up ..."
    rm_other_than $TMP1 $DIRNAME run.sh
    exit 0
fi

if [[ ! -f $TEST_DEBUG_FILE_PATH ]]
then
    error_message "$TEST_DEBUG_FILE_PATH not present"
    exit 2
fi

$SSTTG_DEV_ROOT/dbg_formatter.sh -p $TEST_DEBUG_FILE_PATH > out.txt

