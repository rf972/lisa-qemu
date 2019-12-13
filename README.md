### Introduction

This repo provides an integration which allows LISA to work with QEMU VMs.<br/>
LISA's goal is to help Linux kernel developers to measure the impact of modifications in core parts of the kernel.<br/>
Integration with QEMU will allow developers to test large veriety of hardware configurations including ARM architecture<br/>
and complex NUMA topologies.

### Getting Started
```
git clone https://github.com/rf972/lisa-qemu.git
cd lisa-qemu
git submodule update --init --recursive
cd external/lisa
sudo ./install_base.sh)
source init_env
```

In case the venv becomes unusable for some reason,<br/>
the `lisa-install` shell command available after sourcing init_env<br/>
will allow to create a new clean venv from scratch.<br/>

### For more information please refer to LISA documentation
https://lisa-linux-integrated-system-analysis.readthedocs.io/en/master/setup.html

### Building virtual machine
At top level run<br/>
sh scripts/build-image.sh ubuntu.aarch64 conf/default_config.yml<br/>

Optionally you can provide arguments.<br/>
build.sh [image name] [config yaml]<br/>
    Where:<br/>
      [image name] is one of the scripts from /external/qemu/tests/vm, such as ubuntu.aarch64.<br/>
      [config yaml] Is the configuration file.  See /conf for examples.<br/>

To launch the VM:<br/>
  The build.sh has a line at the end which details how to launch the vm:<br/>

### Build kernel
We have a script (described below), which automates the process of putting a new kernel into your image.

To build the kernel we suggest the following steps <br/>
1) download the kernel from https://github.com/torvalds/linux <br/>
2) copy one of the config files from lisa-qemu/configs over to your top level kernel .config file. <br/>
3) make menuconfig <br/>
4) make bindeb-pkg -j [number of processors] <br/>

The resulting .deb package will be named something like this: <br/>
linux-image-5.4.0+_5.4.0+-4_arm64.deb<br/>

### Install kernel into virtual machine <br/>
A script is provided to simplify the process of adding a kernel image to the virtual machine. <br/>

At the top level of lisa-qemu, run<br/>
python3 scripts/install-kernel.py -i [image] -v [kernel version] -p [kernel .deb package]<br/>

Example:<br/>
python3 -i ../external/qemu/build/ubuntu.aarch64.img -v 5.4.0+ -p linux-image-5.4.0+_5.4.0+-4_arm64.deb    <br/>
    
### License
This project is licensed under Apache-2.0.<br/>
This project includes some third-party code under other open source licenses.<br/>

### Contributions / Pull Requests
Contributions are accepted under Apache-2.0.<br/>
Only submit contributions where you have authored all of the code.<br/>
If you do this on work time make sure your employer is cool with this.<br/>
