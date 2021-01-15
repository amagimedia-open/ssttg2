#!/bin/bash

set -e
set -u
set -x

find test -name 'out*' -exec rm -vf {} \;

docker build -t ssttg2_rel -f dockerfile_rel.txt .
