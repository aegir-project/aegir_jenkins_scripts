#!/bin/sh

# For now just check that the incomming directory is empty again.
if [ `ls -A /srv/reprepro/incoming` ]
then
  echo /srv/reprepro/incoming still has files... something is not OK
  exit 1
else
  echo "/srv/reprepro/incoming is empty as expected"
fi

