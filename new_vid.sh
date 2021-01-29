#!/bin/bash

# Gets the directory path of this file
PROGRAM_DIR=$(dirname "$(realpath $0)")

# Temporarily move into this directory
pushd $PROGRAM_DIR

#Activate venv, run program, then deactivate
source venv/bin/activate
python3 main.py
deactivate

# Move back to whatever directory you were in previously
popd