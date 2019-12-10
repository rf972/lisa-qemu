Introduction
==================
This repo provides an integration which allows LISA to work with QEMU VMs.

Getting Started
==================
To build:
$ scripts/build.sh

Optionally you can provide arguments.<P>
build.sh [image name] [config yaml]<p>
    Where:<p>
      [image name] is one of the scripts from /external/qemu/tests/vm, such as ubuntu.aarch64.<p>
      [config yaml] Is the configuration file.  See /conf for examples.<p>

To launch the VM:<p>
  The build.sh has a line at the end which details how to launch the vm:
