#!/bin/bash

if [ "$1" = "local" ]
then
    REPO=..
elif [ "$1" = "remote" ]
then
	REPO=git@github.com:danielnyga/pracmln
else
	echo specify either "local" or "remote"
	exit -1
fi


cd $PRACMLN_HOME/test
echo cloning pracmln temporarily from $REPO
mkdir src
# rsync -qa .. src --exclude test
git clone --branch release $REPO src 
docker build -t pracmln/test .
echo Removing temporary files...
rm -rf src