#!/bin/sh

docker build -t aegir3_build_env .

# Jenkins provides a build number.
#export BUILD_NUMBER=42

docker run \
       --volume=/srv/reprepro/incoming:/incoming \
       --volume=/var/lib/jenkins/.gnupg:/root/.gnupg:ro \
       --env=BUILD_NUMBER=$BUILD_NUMBER \
       aegir3_build_env

# debug
#docker run -it aegir3_build_env /bin/bash
