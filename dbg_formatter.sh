#!/bin/bash

set -u
#set -x

#----[globals]------------------------------------------------------------------------

DIRNAME=$(readlink -e $(dirname $0))
MODNAME=$(basename $0)
TERMINATED=0

#----[sources]---------------------------------------------------------------

source $DIRNAME/common_bash_functions.sh

#----[options]---------------------------------------------------------------

OPT_PROGRESS=0
OPT_DEBUG_FILEPATH=""

#----[temp files and termination]--------------------------------------------

function fnxOnEnd
{
    ((TERMINATED)) && { return; }
    rm $TMP1 $TMP2
    TERMINATED=1
}

TMP1=`mktemp`
TMP2=`mktemp`

trap 'fnxOnEnd;' 0 1 2 3 6 9 11

#----[helper functions]------------------------------------------------------

function usage
{
    cat <<EOD
NAME

    $MODNAME - analyses the debug output of the ssttg.sh script
                   

SYNOPSIS

    $MODNAME [-p] [-h] [debug_filepath]

DESCRIPTION

    $MODNAME analyses the debug output of the ssttg.sh script.
    if debug_filepath is not provided, stdin is used.

OPTIONS

    -p
        display progress on stderr. In this case stdout must be redirected
        to some file/pipe.
        This is optional.

    -h
        Displays this help and quits.
        This is optional.

EOD
}

#----------------------------------------------------------------------------
# MAIN
#----------------------------------------------------------------------------

TEMP=`getopt -o "ph" -n "$0" -- "$@"`
eval set -- "$TEMP"

while true 
do
	case "$1" in
        -p) OPT_PROGRESS=1; shift 1;;
        -h) usage; exit 0;;
		--) shift ; break ;;
		*) echo "Internal error!" ; exit 1 ;;
	esac
done

if [[ $# -gt 0 ]]
then
    OPT_DEBUG_FILEPATH="$1"
    if [[ ! -f $OPT_DEBUG_FILEPATH ]]
    then
        error_message "$OPT_DEBUG_FILEPATH not present"
        exit 1
    fi
fi

#-----------------------------------------------------------

cat $OPT_DEBUG_FILEPATH |\
gawk \
    -v v_opt_progress=$OPT_PROGRESS \
'
    {
        ++line_count

        if (v_opt_progress)
            printf "%08d\r", line_count > "/dev/stderr"
    }

/^audio_depacketizer:info/ \
    {
        #audio_depacketizer:info: pkt-details, time=1611137123, pkt#=00000001, sig=c0ffeeee, ts=0000000000000000, sz=00001024
        #field <ts>

        print "I " extract_field_value($6)+0
        next
    }

/com.amagi.stt.PCMGenerator, Received-data/ \
    {
        #INFO, com.amagi.stt.PCMGenerator, Received-data, pts=32, len=1024
        #field <pts>

        print "G " extract_field_value($4)
        next
    }

/com.amagi.stt.PCMStreamState, get_data_from_pts/ \
    {
        #INFO, com.amagi.stt.PCMStreamState, get_data_from_pts, pts=-240000, hpts=0, tpts=0, status=True
        #field <pts>

        print "B " extract_field_value($4)
        next
    }

/com.amagi.stt.PCMStreamState, Resending/ \
    {
        #INFO, com.amagi.stt.PCMStreamState, Resending, data_ms=64.0
        #field <data_ms>

        print "R " extract_field_value($4)
        next
    }

/com.amagi.stt.SRTWriter, transcript=/ \
    {
        #INFO, com.amagi.stt.SRTWriter, transcript=in a;; stability=0.8999999761581421;; end_sec=34;; end_nanos=690.0;; time=1611137591.2510517;; is_final=False
        log_line = $0
        sub(/^.*SRTWriter, /, "", log_line)
        print "T " log_line
        next
    }

/com.amagi.stt.SRTWriter, srt_out/ \
    {
        #INFO, com.amagi.stt.SRTWriter, srt_out, text=1 0000000:00:34,000 --> 0000000:00:34,800 in a  
        log_line = $0
        sub(/^.*srt_out, text=/, "", log_line)
        print "S " log_line
        next
    }

    END \
    {
        if (v_opt_progress)
            printf "\n" > "/dev/stderr"
    }

    function extract_field_value(from, _t_arr)
    {
        split(from, _t_arr, /[=,]/)
        return _t_arr[2]
    }
'


