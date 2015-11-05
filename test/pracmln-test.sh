#!/bin/bash

cd $PRACMLN_HOME/test
echo Copying pracmln temporarily...
mkdir src
rsync -qa .. src --exclude test
docker build -t pracmln/test .
echo Removing temporary files...
rm -rf src