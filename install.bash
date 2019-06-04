#!/usr/bin/env bash
# Installs ETA and its dependencies
#
# Copyright 2017-2019, Voxel51, Inc.
# voxel51.com
#
# Brian Moore, brian@voxel51.com
#


# Show usage information
usage() {
    echo "Usage:  bash $0 [-h] [-l] [-bp]

Getting help:
-h      Display this help message.

Custom installations:
-l      Perform a lite install, which omits submodules and other items not
        required to use the core library. The default is a full install.

Mac-only options:
-b      Use brew to install packages (mac only). The default is false.
-p      Use port to install packages (mac only). The default is true.
"
}


# Parse flags
SHOW_HELP=false
LITE_INSTALL=false
USE_MACPORTS=true
while getopts "hlbp" FLAG; do
    case "${FLAG}" in
        h) SHOW_HELP=true ;;
        l) LITE_INSTALL=true ;;
        b) USE_MACPORTS=false ;;
        p) USE_MACPORTS=true ;;
        *) usage ;;
    esac
done
[ ${SHOW_HELP} = true ] && usage && exit 0


CWD=$(pwd)

EXTDIR=external
EXTLOG="${CWD}/${EXTDIR}/install.log"
EXTERR="${CWD}/${EXTDIR}/install.err"

mkdir -p "${EXTDIR}"
rm -rf "${EXTLOG}"
rm -rf "${EXTERR}"

OS=$(uname -s)

set -o pipefail


# Run command and print stdout/stderr to terminal and (separate) logs
INFO () {
    ("$@" | tee -a "${EXTLOG}") 3>&1 1>&2 2>&3 | tee -a "${EXTERR}"
}


# Print message and log to stderr log
WARN () {
    printf "***** WARNING: ${1}\n" 2>&1 | tee -a "${EXTERR}"
}


# Print message and log to stdout log
MSG () {
    INFO printf "***** ${1}\n"
}


# Exit by printing message and locations of log files
EXIT () {
    MSG "${1}"
    MSG "Log file: ${EXTLOG}"
    MSG "Error file: ${EXTERR}"
    exit 0
}


# Run command, log stdout/stderr, and exit upon error
CRITICAL () {
    INFO "$@"
    if [ $? -ne 0 ]; then
        if [[ ${LITE_INSTALL} = true ]]; then
            EXIT "LITE INSTALLATION FAILED"
        else
            EXIT "INSTALLATION FAILED"
        fi
    fi
}


if [[ ${LITE_INSTALL} = true ]]; then
    MSG "LITE INSTALLATION STARTED"
else
    MSG "INSTALLATION STARTED"
fi


# GPU flag
MSG "Checking system for GPU"
if [ "${OS}" == "Linux" ]; then
    lspci | grep -q "NVIDIA"
    if [ $? -eq 0 ]; then
        GCARD=ON
    else
        GCARD=OFF
    fi
elif [ "${OS}" == "Darwin" ]; then
    GCARD=OFF
fi
MSG "Setting GCARD=${GCARD}"


# Install base packages
MSG "Installing base machine packages"
if [ "${OS}" == "Linux" ]; then
    CRITICAL sudo apt-get update
    CRITICAL sudo apt-get -y install build-essential
    CRITICAL sudo apt-get -y install pkg-config
    CRITICAL sudo apt-get -y install python-pip
    CRITICAL sudo apt-get -y install python-dev
    CRITICAL sudo apt-get -y install cmake
    CRITICAL sudo apt-get -y install cmake-data
    CRITICAL sudo apt-get -y install unzip
elif [ "${OS}" == "Darwin" ]; then
    # Macs already have most goodies, so just update package managers
    if [ ${USE_MACPORTS} = true ]; then
        CRITICAL sudo port selfupdate
    else
        CRITICAL brew update
    fi
fi
CRITICAL pip install --upgrade pip
CRITICAL pip install --upgrade virtualenv


MSG "Installing Python packages"
CRITICAL pip install -r requirements.txt


# Install Tensorflow
if [ "${GCARD}" == "ON" ]; then
    #
    # Supported tensorflow-gpu + CUDA configurations
    # https://www.tensorflow.org/install/install_sources#tested_source_configurations
    #
    if [ $(cat /usr/local/cuda/version.txt | grep -c "CUDA Version 8") -gt 0 ]; then
        # Found CUDA 8, so we must install an old version
        MSG "Installing tensorflow-gpu 1.4"
        CRITICAL pip install --upgrade tensorflow-gpu==1.4.0
    elif [ $(cat /usr/local/cuda/version.txt | grep -c "CUDA Version 9") -gt 0 ]; then
        # Found CUDA 9, so we must install version 1.12.0
        MSG "Installing tensorflow-gpu 1.12.0"
        CRITICAL pip install --upgrade tensorflow-gpu==1.12.0
    else
        MSG "Installing latest tensorflow-gpu"
        CRITICAL pip install --upgrade tensorflow-gpu
    fi
else
    MSG "Installing tensorflow 1.12.0"
    CRITICAL pip install --upgrade tensorflow==1.12.0
fi


MSG "Installing ETA"
CRITICAL pip install -e .


# Install ffmpeg
INFO command -v ffmpeg
if [ $? -eq 0 ]; then
    MSG "ffmpeg already installed"
else
    MSG "Installing ffmpeg"
    if [ "${OS}" == "Linux" ]; then
        CRITICAL sudo apt-get -y install ffmpeg
    elif [ "${OS}" == "Darwin" ]; then
        if [ ${USE_MACPORTS} = true ]; then
            CRITICAL sudo port install ffmpeg
        else
            CRITICAL brew install ffmpeg
        fi
    fi
fi


# Install imagemagick
INFO command -v convert
if [ $? -eq 0 ]; then
    MSG "imagemagick already installed"
else
    MSG "Installing imagemagick"
    if [ "${OS}" == "Linux" ]; then
        CRITICAL sudo apt-get -y install imagemagick
    elif [ "${OS}" == "Darwin" ]; then
        if [ ${USE_MACPORTS} = true ]; then
            CRITICAL sudo port install imagemagick
        else
            CRITICAL brew install imagemagick
        fi
    fi
fi


# Handle lite installation
if [[ ${LITE_INSTALL} = true ]]; then
    EXIT "LITE INSTALLATION COMPLETE"
fi


# Initialize submodules
MSG "Initializing submodules"
CRITICAL git submodule init
CRITICAL git submodule update

#
# Install tensorflow/models
#
# This requires compiling protocol buffers, which, in turn requires a suitable
# version of `protoc` to be installed on your machine. ETA's `requirements.txt`
# file attempted to install `protoc`, but, if that didn't work, then the code
# below will try to install it another way.
#
# NOTE: If you don't have proctoc>=3.6.1, you may get errors when the `protoc`
# command below runs. To manually install a recent protoc version, follow these
# instructions:
# https://gist.github.com/sofyanhadia/37787e5ed098c97919b8c593f0ec44d8
#
# As of this writing, we recommend installing protoc==3.6.1. Prebuilt binary:
# https://github.com/google/protobuf/releases/download/v3.6.1/protoc-3.6.1-linux-x86_64.zip
#
MSG "Installing tensorflow/models"
cd tensorflow/models
INFO command -v protoc
if [ $? -eq 0 ]; then
    MSG "protoc already installed"
else
    MSG "Installing protoc"
    if [ "${OS}" == "Darwin" ]; then
        # Mac
        CRITICAL brew install protobuf
     else
        # Linux
        CRITICAL sudo apt-get install -y protobuf-compiler
    fi
fi
MSG "Compiling protocol buffers"
CRITICAL protoc research/object_detection/protos/*.proto \
    --proto_path=research \
    --python_out=research
MSG "You must have '$(pwd)/research' in 'pythonpath_dirs' in your ETA config"
MSG "You must have '$(pwd)/research/slim' in 'pythonpath_dirs' in your ETA config"
cd ../..


EXIT "INSTALLATION COMPLETE"
