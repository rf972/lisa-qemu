#!/bin/sh
set -e

#
# Copyright 2019 Linaro
#
# Build script for lisa-qemu
#
# build-image.sh [qemu image] [config yaml]
#
#    [qemu image] is a name of a qemu image.
#                 Available options are those under lisa-qemu/external/qemu/tests/vm 
#                 such as ubuntu.aarch64
#    [config yaml] is a yaml file with format similar to those 
#                  under lisa-qemu/conf
if [ "$#" -ne "2" ]; then
    echo "USAGE: build-image.sh [qemu image] [config yaml]"
    echo "Builds a new qemu image for use with lisa."
    echo ""
    echo "mandatory arguments:"
    echo "    [qemu image] is a name of a qemu image."
    echo "                 Available options are those under lisa-qemu/external/qemu/tests/vm"
    echo "                 such as ubuntu.aarch64"
    echo "    [config yaml] is a yaml file with format similar to those "
    echo "                  under lisa-qemu/conf"
    echo ""
    echo "examples:" 
    echo "  build-image.sh ubuntu.aarch64 config_example.yaml"
    echo ""
    exit 1
fi           
# Default to using the ubuntu.aarch64 image.
if [ "$1" = "" ]; then
    echo "No argument for image, using ubuntu.aarch64 by default"
    IMAGE="ubuntu.aarch64"
else
    IMAGE=$1
fi

# If there is no yml provided, then
if [ "$2" = "" ]; then
    CONF_YML=""
else

    CONF_YML="QEMU_CONFIG=$(realpath $2)"
fi

###################
# Build qemu
##################
BASEDIR=$(dirname "$0")
cd ${BASEDIR}/../external/qemu/
mkdir build || true
cd build
echo $0 ": CONFIGURE QEMU"
../configure
echo $0 ": MAKE QEMU"
make -j

###################
# Build qemu image
##################


echo $0": BUILD QEMU IMAGE: "${IMAGE}

ENV_VARS="QEMU=./aarch64-softmmu/qemu-system-aarch64 ${CONF_YML}"

env ${ENV_VARS} python3 -B ../tests/vm/${IMAGE}  --image "./${IMAGE}.img" --debug --force --build-image "./${IMAGE}.img" 

# Below is the cmd line for launching the image and ssh to it.
#echo "Launching image"
#env ${ENV_VARS} python3 -B ../tests/vm/${IMAGE}  --debug --image "./${IMAGE}.img" --interactive false