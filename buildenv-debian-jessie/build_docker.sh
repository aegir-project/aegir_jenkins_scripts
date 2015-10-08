#!/bin/sh

docker build -t aegir3_build_env .
export BUILD_NUMBER=42
#docker run -it --volume=/srv/reprepro/incoming:/incoming aegir3_build_env 
docker run -it --volume=/tmp/newpkg:/incoming \
       --volume=/tmp/newpkg:/incoming \
       --volume=/var/lib/jenkins/.gnupg:/root/.gnupg:ro \
       --env=BUILD_NUMBER=$BUILD_NUMBER \
       aegir3_build_env

# debug
#docker run -it aegir3_build_env /bin/bash

# Cleanup
#rm -r .gnupg
