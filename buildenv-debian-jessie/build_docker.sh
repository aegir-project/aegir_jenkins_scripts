#!/bin/sh

docker build -t aegir3_build_env .

RET=$?
if [ "$RET" != 0 ]; then
  echo "Building docker container failed, not starting package build."
  exit 1
fi


# Jenkins provides a build number, fallback to 42
#if [ -z "$BUILD_NUMBER" ]; then
#  export BUILD_NUMBER=42
#fi

PWD=`pwd`
SCRIPT_DIR=`dirname $PWD`
PROVISION_DIR=`dirname $SCRIPT_DIR`/provision

docker run \
       --volume=/srv/reprepro/incoming:/incoming \
       --volume=/var/lib/jenkins/.gnupg:/root/.gnupg:ro \
       --volume=$PROVISION_DIR:/root/provision \
       --volume=$SCRIPT_DIR:/root/aegir_jenkins_scripts \
       --env=BUILD_NUMBER=$BUILD_NUMBER \
       aegir3_build_env

# debug
#docker run -it aegir3_build_env /bin/bash
