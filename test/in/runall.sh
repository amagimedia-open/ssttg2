#!/bin/bash

set -u
#set -x

OPT_CLEAN=""
[[ ${1-""} = "clean" ]] && { OPT_CLEAN="clean"; }

#----[temp files and termination]--------------------------------------------

function fnxOnEnd
{
    rm $TMP1 $TMP2
}

TMP1=`mktemp`
TMP2=`mktemp`

trap 'fnxOnEnd;' 0 1 2 3 6 9 11

#----[test cases]------------------------------------------------------------

cat <<EOD >$TMP1
$SSTTG_DEV_ROOT/test/in/01/run.sh
$SSTTG_DEV_ROOT/test/in/02/run.sh
$SSTTG_DEV_ROOT/test/in/03/run.sh
$SSTTG_DEV_ROOT/test/in/04/run.sh
EOD

#----[main]------------------------------------------------------------------

for test_script_path in $(cat $TMP1)
do
    if [[ $test_script_path =~ ^# ]]
    then
        echo "skipping $test_script_path"
    else
        echo "executing $test_script_path $OPT_CLEAN" # | boxes -d stone >&2
        $test_script_path $OPT_CLEAN
    fi
    echo
done

