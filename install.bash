#!/usr/bin/env bash
# Installs ETA and its dependencies.
#
# Copyright 2017-2020, Voxel51, Inc.
# voxel51.com
#


# Show usage information
usage() {
    echo "Usage:  bash $0 [-h] [-l] [-d] [-bp]

Getting help:
-h      Display this help message.

Custom installations:
-l      Perform a lite install, which omits submodules and other items not
        required to use the core library. The default is a full install.
-d      Install developer dependencies. The default is false.

Mac-only options:
-b      Use brew to install packages (mac only). The default is true.
-p      Use port to install packages (mac only). The default is false.
"
}


# Parse flags
SHOW_HELP=false
LITE_INSTALL=false
DEV_INSTALL=false
USE_MACPORTS=false
while getopts "hldbp" FLAG; do
    case "${FLAG}" in
        h) SHOW_HELP=true ;;
        l) LITE_INSTALL=true ;;
        d) DEV_INSTALL=true ;;
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


# Abort installation by printing message and exiting
ABORT () {
    EXIT "INSTALLATION ABORTED: $1"
}


if [[ ${LITE_INSTALL} = true ]]; then
    MSG "LITE INSTALLATION STARTED"
else
    MSG "INSTALLATION STARTED"
fi


# Check for `python` binary
MSG "Checking for 'python' binary"
PYTHON_BINARY=$(command -v python)
if [[ ! -z "${PYTHON_BINARY}" ]]; then
    MSG "Using 'python' binary at '${PYTHON_BINARY}'"
else
    ABORT "No 'python' binary found"
fi


# Check Python version
MSG "Checking version of 'python' binary"
PYTHON_VERSION=$(python -c 'import platform; print(platform.python_version())')
if [[ $PYTHON_VERSION == "3.6."* ]] || [[ $PYTHON_VERSION == "2.7."* ]]; then
    MSG "Found compatible version: Python ${PYTHON_VERSION}"
else
    WARN "Python 3.6.X or 2.7.X are recommended, but Python $PYTHON_VERSION was found"
    read -p "Are you sure you want to continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        ABORT "Unsupported Python version"
    fi
fi


# Check for `pip` binary
MSG "Checking for 'pip' binary"
PIP_BINARY=$(command -v pip)
if [[ ! -z "${PIP_BINARY}" ]]; then
    MSG "Using 'pip' binary at '${PIP_BINARY}'"
else
    ABORT "No 'pip' binary found"
fi


# Check that specified package manager is installed in Mac OS
if [ "${OS}" == "Darwin" ]; then
    if [ ${USE_MACPORTS} = true -a -z "$(which port)" ]; then
        ABORT "MacPorts specified, but 'port' application not found"
    elif [ ${USE_MACPORTS} = false -a -z "$(which brew)" ]; then
        ABORT "Homebrew specified, but 'brew' application not found"
    fi
fi


# GPU flag
MSG "Checking system for GPU"
if [ "${OS}" == "Linux" ]; then
    grep -q "NVIDIA" <(lspci)
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
    CRITICAL sudo apt-get -y install cmake
    CRITICAL sudo apt-get -y install cmake-data
    CRITICAL sudo apt-get -y install unzip
elif [ "${OS}" == "Darwin" ]; then
    if [ ${USE_MACPORTS} = true ]; then
        CRITICAL sudo port selfupdate
    else
        CRITICAL brew update
    fi
fi


MSG "Installing Python packages"
if [ ${DEV_INSTALL} = true ]; then
    MSG "Performing dev install"
    CRITICAL pip install -r requirements/dev.txt
else
    CRITICAL pip install -r requirements.txt
fi


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
    elif [ $(cat /usr/local/cuda/version.txt | grep -c "CUDA Version 10") -gt 0 ]; then
        # Found CUDA 10, so we must install version 1.14.0
        MSG "Installing tensorflow-gpu 1.14.0"
        CRITICAL pip install --upgrade tensorflow-gpu==1.14.0
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


# @note(lite) handle lite installation
if [[ ${LITE_INSTALL} = true ]]; then
    EXIT "LITE INSTALLATION COMPLETE"
fi


# Initialize submodules
MSG "Initializing submodules"
CRITICAL git submodule init
CRITICAL git submodule update

MSG "Installing tensorflow/models"
cd tensorflow/models
INFO command -v protoc
if [ $? -eq 0 ]; then
    MSG "protoc already installed"
else
    MSG "Installing protoc"
    if [ "${OS}" == "Darwin" ]; then
        # Mac - Download Protoc from GitHub
        CRITICAL curl -OL https://github.com/protocolbuffers/protobuf/releases/download/v3.6.1/protoc-3.6.1-osx-x86_64.zip
        CRITICAL unzip protoc-3.6.1-osx-x86_64.zip -d protoc3
        CRITICAL rm -rf protoc-3.6.1-osx-x86_64.zip
     else
        # Linux - Download Protoc from GitHub
        CRITICAL curl -OL https://github.com/protocolbuffers/protobuf/releases/download/v3.6.1/protoc-3.6.1-linux-x86_64.zip
        CRITICAL unzip protoc-3.6.1-linux-x86_64.zip -d protoc3
        CRITICAL rm -rf protoc-3.6.1-linux-x86_64.zip
    fi

    # Move protoc to /usr/local
    CRITICAL sudo mv protoc3/bin/* /usr/local/bin/
    CRITICAL sudo mv protoc3/include/* /usr/local/include/
    CRITICAL rm -rf protoc3
fi

MSG "Compiling protocol buffers"
CRITICAL protoc research/object_detection/protos/*.proto \
    --proto_path=research \
    --python_out=research
MSG "You must have '$(pwd)/research' in 'pythonpath_dirs' in your ETA config"
MSG "You must have '$(pwd)/research/slim' in 'pythonpath_dirs' in your ETA config"

cd ../..


EXIT "INSTALLATION COMPLETE"
