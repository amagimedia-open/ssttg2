#!/bin/bash

set -u
set -x

docker exec \
        -it \
        --privileged \
        -w /ssttg \
        ssttg2_dev_c \
        bash
