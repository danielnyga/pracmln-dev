#!/bin/bash

if [ "$1" = "local" ]
then
    REPO=..
elif [ "$1" = "remote" ]
then
	REPO=git@github.com:danielnyga/pracmln
elif [ "$1" = "uncommitted" ]
then
	echo
else
	echo specify either "local", "remote" or "uncommitted"
	exit -1
fi


cd $PRACMLN_HOME/test
mkdir src
if [ "$1" = "uncommitted" ]
then
	echo copying uncommitted state of local repo...
	rsync -qa .. src --exclude test
else
	echo cloning pracmln temporarily from $REPO
	git clone --branch release $REPO src
fi 
docker build -t pracmln/test .
echo Removing temporary files...
rm -rf src