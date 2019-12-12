Introduction
==================
This repo provides an integration which allows LISA to work with QEMU VMs.
LISA's goal is to help Linux kernel developers to measure the impact of modifications in core parts of the kernel.
Integration with QEMU will allow developers to test large veriety of hardware configurations including ARM architecture
and complex NUMA topologies.

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

License
==================
This project is licensed under Apache-2.0.
This project includes some third-party code under other open source licenses.
