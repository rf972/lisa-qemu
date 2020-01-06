#
# Copyright 2019 Linaro
#
# Script to run inside a VM to remove all but a 
# single kernel from the boot sequence.
# This just ensures that the kernel we want to boot
# is guaranteed to be the one that starts regardless of version.
#
# install_kernel.py -i [image] -v [kernel version] -p [kernel .deb package]
# Where:
#    [image] is an image built via build-image.sh
#    [kernel version] is a string like 5.5.0 or 5.5.0.rc1+
#    [kernel .deb package] is a kernel package built via 
#                          a kernel make bindeb-pkg
#

import glob
import shutil
import sys
import os
import subprocess
from subprocess import Popen,PIPE
import argparse
from argparse import RawTextHelpFormatter
import traceback
import re

                
class install_kernel:
    mount_path = "./mnt"
    host_tmp = "/tmp"
    mount_tmp = os.path.join(mount_path, "tmp")
    qemu_static_path = "/usr/bin"
    qemu_static_name = "qemu-aarch64-static" 
    qemu_cpy_cmd = "cp /usr/bin/qemu-aarch64-static ./mnt/usr/bin"
    kernel_pkg_cpy_cmd = "cp {} /tmp"
    install_kernel_cmd = "sudo /usr/bin/dpkg --force-all -i {}"
    install_kernel_cmd_chroot = "/usr/bin/dpkg --force-all -i {}"
    host_dir_mounts = ["tmp", "dev","proc","sys"]
    install_pkg_path = os.path.join(mount_path, "install_kernel")
    install_pkg_vm_path = "/install_kernel"
    move_kernel_script = "move-kernels.py"
    move_kernel_script_path = os.path.join(install_pkg_vm_path, move_kernel_script)    
    launch_cmd = "env {} python3 -B ../tests/vm/{} --image {} --debug {}"
    default_image_type = "ubuntu.aarch64"
    default_image_name = "{}.img".format(default_image_type)
    default_config_file = "conf/conf_default.yml"
    build_path_rel = "build"
    
    def __init__(self):
        self._image_mounted = False
        
        self.device = None
        self._script_path = os.path.dirname(os.path.realpath(__file__))
        self._root_path = os.path.realpath(os.path.join(self._script_path, "../"))
        self._qemu_path = os.path.realpath(os.path.join(self._root_path, "external/qemu/build"))
        self._mount_path = os.path.realpath(os.path.join(self._qemu_path, self.mount_path))
        
        if 'QEMU_CONFIG' in os.environ:
            self._default_config_path = os.environ['QEMU_CONFIG']
        else:
            self._default_config_path = os.path.realpath(os.path.join(self._root_path, 
                                                        self.default_config_file))
        self.build_path = os.path.realpath(os.path.join(self._root_path, self.build_path_rel))
        self._image_dir_path = os.path.join(self.build_path, "VM-" + "ubuntu.aarch64")
        self._default_image_path = os.path.join(self._image_dir_path, self.default_image_name)
        self.parse_args()
        self._image_path = os.path.abspath(getattr(self._args, 'image'))
        self._image_dir_path = os.path.dirname(self._image_path)
        self.continue_on_error = self._args.debug
        self._raw_image_path = self._image_path + '.raw'
        self.kernel_ver = self._args.kernel_ver
        self._kernel_pkg_name = os.path.basename(self._args.kernel_pkg)
        self._kernel_pkg_path = os.path.abspath(self._args.kernel_pkg)
        self.get_kernel_version()
        self._output_image_path = self._image_path + '.kernel-' + self.kernel_ver
        self._config_path = os.path.abspath(self._args.config)
        self._install_pkg_vm_path =os.path.join(self.install_pkg_vm_path, self._kernel_pkg_name)
        self.chroot_cmd = "chroot {} {}".format(self._mount_path, 
                                                os.path.join(self.qemu_static_path, 
                                                             self.qemu_static_name))
        self.print("image_path: " + self._image_path)
        self.print("kernel_pkg_name: " + self._kernel_pkg_name)
        
    def print(self, trace):
        print("{}: {}".format(sys.argv[0], trace))
            
    def terminate(self, err):
        if not self.continue_on_error:
            exit(err)
            
    def issue_cmd(self, cmd, fail_on_err=True, err_msg=None, enable_stdout=True, no_capture=False):
        rc, output = self.run_command(cmd, enable_stdout=enable_stdout, no_capture=no_capture)
        if fail_on_err and rc != 0:
            self.print("cmd failed with status: {} cmd: {}".format(rc, cmd))
            if (err_msg):
                self.print(err_msg)
            self.terminate(1)
        return rc, output
    
    def run_command(self, command, enable_stdout=True, no_capture=False):
        output_lines = []
        if self._args.debug:
            print("{}: {}".format(sys.argv[0], command))
        if self._args.dry_run:
            print("")
            return 0, output_lines
        if no_capture:
            rc = subprocess.call(command, shell=True)
            return rc, output_lines
        process = subprocess.Popen(command.split(), stdout=subprocess.PIPE) #shlex.split(command)
        while True:
            output = process.stdout.readline()
            if (not output or output == '') and process.poll() is not None:
                break
            if output and enable_stdout:
                self.print(str(output, 'utf-8').strip())
            output_lines.append(str(output, 'utf-8'))
        rc = process.poll()
        return rc, output_lines
    
    def parse_args(self):
        parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter,
                                         description="Installs a kernel into an image and " \
                                         "activates this as the kernel to use on next boot.\n",
                                         epilog="examples:\n"\
                                         "   To select all defaults.  Only kernel package is required: \n"\
                                         "     install_kernel.py -p linux-image-5.4.0+_5.4.0+-4_arm64.deb\n"\
                                         "   Or provide one or more arguments\n"
                                         "     install_kernel.py -i ../external/qemu/build/ubuntu.aarch64.img \\\n"\
                                         "                       -p linux-image-5.4.0+_5.4.0+-4_arm64.deb\n")
        parser.add_argument("--debug", "-D", action="store_true",
                            help="enable debug output")
        parser.add_argument("--dry_run", action="store_true",
                            help="for debugging.  Just show commands to issue.")
        parser.add_argument("--vm", action="store_true",
                            help="Install kernel using a vm instead of a chroot.")
        parser.add_argument("--image", "-i", default=self._default_image_path,
                            help="vm image file name.\n"\
                            "ex. -i ../external/qemu/build/ubuntu.aarch64.img")
        parser.add_argument("--kernel_ver", "-v", default="",
                            help="kernel version like: -v 5.4.0+")
        parser.add_argument("--kernel_pkg", "-p", default="", required=True,
                            help="kernel package to use")
        parser.add_argument("--config", "-c", default=self._default_config_path,
                            help="config file. \n"\
                            "default is conf/conf_default.yml")
        self._args = parser.parse_args()
        
        for arg in ['image', 'kernel_ver', 'kernel_pkg']:
            if getattr(self._args, arg):
                self.print("{}: {}".format(arg, getattr(self._args, arg)))

    def convert_image(self, type, file_in, file_out):
        self.print("Converting to image type {} {} -> {}".format(type, file_in, file_out))
        cmd = "qemu-img convert -p -O {} {} {}".format(type, file_in, file_out)
        self.issue_cmd(cmd, enable_stdout=False)

        os.chmod(file_out, 0o666)
        
    def create_loopback(self):
        self.print("create loopback device for {}".format(self._raw_image_path))
        rc, unused = self.issue_cmd("losetup -f -P {}".format(self._raw_image_path),
                                    err_msg="could not create loopback device")
        
        rc, devices = self.issue_cmd("losetup -l", enable_stdout=False)
        for line in devices:
            if self._raw_image_path in line:
                for field in line.split(" "):
                    if 'loop' in field:
                        self.device = field
        if self.device == None or "/loop" not in self.device:
            self.print("could not create loopback device")
            self.terminate(1)
        self.print("loopback device is: {}".format(self.device))
        
    def destroy_loopback(self):
        self.print("destroy loopback device {}".format(self.device))
        self.issue_cmd("losetup -d {}".format(self.device),
                       err_msg="could not destroy loopback device", 
                       fail_on_err=False)
        
    def mount_host_dirs(self):
        self.print("mount host directories into {}".format(self._mount_path))
        mounts = [{'src': "/" + a, 'dst': os.path.join(self._mount_path, a)} for a in self.host_dir_mounts]
        for mnt in mounts:
            self.issue_cmd("mount --bind {} {}".format(mnt['src'], mnt['dst']))
        
    def umount_host_dirs(self):
        self.print("umount host directories from {}".format(self._mount_path))
        mounts = [{'src': "/" + a, 'dst': os.path.join(self._mount_path, a)} for a in self.host_dir_mounts]
        for mnt in mounts:
            self.issue_cmd("umount {}".format(mnt['dst']), fail_on_err=False)
        
    def mount_image(self):                
        if not os.path.exists(self._mount_path):
            self.print("creating {}".format(os.path.abspath(self._mount_path)))
            os.mkdir(self._mount_path)
        self.create_loopback()        
        # After this point, we have to cleanup before exiting.
        self._image_mounted = True
        self.print("mount image to {}".format(os.path.abspath(self._mount_path)))
        rc, unused = self.issue_cmd("mount {}p1 {}".format(self.device, self._mount_path))
        self.mount_host_dirs()
        
    def umount_image(self):
        self.umount_host_dirs()
        self.print("umount image from {}".format(self._mount_path))
        rc, unused = self.issue_cmd("umount {}".format(self._mount_path), fail_on_err=False)
        self.destroy_loopback()
        self._image_mounted = False
        os.rmdir(self._mount_path)
        
    def copy_qemu_static(self):
        self.issue_cmd(self.qemu_cpy_cmd)
        
    #
    # We move older versions out of the way so that when we
    # do update grub it finds just the relevant version.
    #
    def move_old_kernels(self, root_path="/"):
        src_path = os.path.join(self._mount_path, "boot")
        dest_path = os.path.join(src_path, "backup")
        if not os.path.exists(dest_path):
            os.mkdir(dest_path)
        copy_patterns = ['initrd.img*', 'vmlinuz*']
        
        self.print("move old kernels out of the way.")
        for pattern in copy_patterns:
            for file in glob.glob(os.path.join(src_path, pattern)):
                if (self.kernel_ver not in file):
                    self.print("move {} to {}".format(file, dest_path))
                    cmd = "mv {} {}".format(file, dest_path)
                    self.issue_cmd(cmd)

    def get_kernel_version(self):
        if self.kernel_ver:
            return
         #Description: Linux kernel, version 5.4.0+
        cmd = "dpkg --info {}".format(self._kernel_pkg_path)
        rc, output = self.issue_cmd(cmd)
        self.kernel_ver = None
        for line in output:
            if "Source: linux-" in line:
                search = re.search(r'Source: linux-([\d.]+.+)$', line)
                if search != None and len(search.groups()) > 0:
                    self.kernel_ver = search.group(1)
        if self.kernel_ver == None:
            raise Exception("Unable to determine kernel version, please use --kernel_ver argument.")
        self.print("Kernel version is: {}".format(self.kernel_ver))

    def install_pkg(self):
        cmd = self.kernel_pkg_cpy_cmd.format(self._kernel_pkg_path)
        self.issue_cmd(cmd)
        
        self.print("install kernel image {}".format(self._kernel_pkg_name))        
        cmd = self.install_kernel_cmd_chroot.format(os.path.join(self.host_tmp, self._kernel_pkg_name))
        chroot_cmd = "{} {}".format(self.chroot_cmd, cmd)
        self.issue_cmd(chroot_cmd, fail_on_err=False)
            
    def copy_files_to_image(self):
        if not os.path.exists(self.install_pkg_path):
            os.mkdir(self.install_pkg_path)
        cmd = "cp {} {}".format(self._kernel_pkg_path, self.install_pkg_path)
        self.issue_cmd(cmd)
        move_script_path = os.path.join(self._root_path, "scripts")
        move_script_path = os.path.join(move_script_path, self.move_kernel_script)
        cmd = "cp {} {}".format(move_script_path, self.install_pkg_path)
        self.issue_cmd(cmd)
        
    def run_cmd_in_vm(self):
        env_vars = "QEMU=./aarch64-softmmu/qemu-system-aarch64 "
        env_vars += "QEMU_CONFIG={} ".format(self._config_path)
        cpy_cmd = "sudo python3 {} {}".format(self.move_kernel_script_path,
                                              self.kernel_ver)
        install_cmd = self.install_kernel_cmd.format(self._install_pkg_vm_path)
        cmd = self.launch_cmd.format(env_vars, "ubuntu.aarch64", self._raw_image_path, 
                                     '"{} ; {}"'.format(cpy_cmd, install_cmd))
        
        self.issue_cmd(cmd, no_capture=True)
        
    def install_kernel_vm(self):
        self.copy_files_to_image()
        self.umount_image()
        self.run_cmd_in_vm()
        
    def install_kernel_chroot(self):
        self.copy_qemu_static()
        # modify the share to move old kernels out of the way.
        self.move_old_kernels()
        # install the new kernel.
        self.install_pkg()
        self.umount_image()
            
    def remove_temporaries(self):
        self.print("remove temporary files")
        if os.path.exists(self._raw_image_path):
            os.remove(self._raw_image_path)

    def cleanup(self):
        if self._image_mounted:
            # Cleanup as needed.
            self.umount_image()
            self.remove_temporaries()    

    def run(self):
        try:
            os.chdir(self._qemu_path)
            # setup, convert image to raw, mount it.
            self.convert_image('raw', self._image_path, self._raw_image_path)
            self.mount_image()
            if self._args.vm:
                self.install_kernel_vm()
            else:
                self.install_kernel_chroot()
            # cleanup and convert image back to qcow2
            self.convert_image('qcow2', self._raw_image_path, self._output_image_path)
            self.remove_temporaries()
            print("Install kernel successful.")
            print("Image path: {}\n".format(self._output_image_path))
        except Exception as e:
            sys.stderr.write("Exception hit\n")
            if isinstance(e, SystemExit) and e.code == 0:
                return 0
            traceback.print_exc()
            return 2
        finally:
            self.cleanup()
        
if __name__ == "__main__":
    inst_obj = install_kernel()    
    inst_obj.run()
