### Introduction

This repo provides an integration which allows LISA to work with QEMU VMs.<br/>
LISA's goal is to help Linux kernel developers to measure the impact of modifications in core parts of the kernel.<br/>
Integration with QEMU will allow developers to test large veriety of hardware configurations including ARM architecture<br/>
and complex NUMA topologies.

### Getting Started
Clone with:<br/>
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
scripts/build.sh<br/>

Optionally you can provide arguments.<br/>
build.sh [image name] [config yaml]<br/>
    Where:<br/>
      [image name] is one of the scripts from /external/qemu/tests/vm, such as ubuntu.aarch64.<br/>
      [config yaml] Is the configuration file.  See /conf for examples.<br/>

To launch the VM:<br/>
  The build.sh has a line at the end which details how to launch the vm:<br/>

### License
This project is licensed under Apache-2.0.<br/>
This project includes some third-party code under other open source licenses.<br/>

### Contributions / Pull Requests
Contributions are accepted under Apache-2.0.<br/>
Only submit contributions where you have authored all of the code.<br/>
If you do this on work time make sure your employer is cool with this.<br/>
