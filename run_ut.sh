#!/bin/bash

set -e
set -u
set -x

gcc -o /ssttg/audio_packetizer   /ssttg/audio_packetizer.c
gcc -o /ssttg/audio_depacketizer /ssttg/audio_depacketizer.c

/ssttg/test/in/runall.sh clean
/ssttg/test/in/runall.sh
