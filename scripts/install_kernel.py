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
import yaml
import base_cmd

                
class InstallKernel(base_cmd.BaseCmd):
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
        super(InstallKernel, self).__init__()
        self._image_mounted = False
        
        self.device = None
        self._script_path = os.path.dirname(os.path.realpath(__file__))
        self._root_path = os.path.realpath(os.path.join(self._script_path, "../"))
        self._qemu_path = os.path.realpath(os.path.join(self._root_path, "external/qemu/build"))
        self._mount_path = os.path.realpath(os.path.join(self._qemu_path, self.mount_path))
        self._qemu_img_path = os.path.join(self._qemu_path, 'qemu-img')
        
        if 'QEMU_CONFIG' in os.environ:
            self._default_config_path = os.environ['QEMU_CONFIG']
        else:
            self._default_config_path = os.path.realpath(os.path.join(self._root_path, 
                                                        self.default_config_file))
        self.build_path = os.path.realpath(os.path.join(self._root_path, self.build_path_rel))
        self._image_dir_path = os.path.join(self.build_path, "VM-" + "ubuntu.aarch64")
        self._default_image_path = os.path.join(self._image_dir_path, self.default_image_name)
        self.parse_args()
        self.set_debug(self._args.debug)
        self.set_dry_run(self._args.dry_run)
        self._image_path = os.path.abspath(getattr(self._args, 'image'))
        self._image_dir_path = os.path.dirname(self._image_path)
        self.vm_config_path = os.path.join(self._image_dir_path, "conf.yml")
        self.continue_on_error = self._args.debug
        self._raw_image_path = self._image_path + '.raw'
        self.kernel_ver = self._args.kernel_ver
        self._kernel_pkg_name = os.path.basename(self._args.kernel_pkg)
        self._kernel_pkg_path = os.path.abspath(self._args.kernel_pkg)
        self.get_kernel_pkg_version(self._kernel_pkg_path)
        self.kernel_config_path = os.path.join(self._image_dir_path,
                                               "conf-kernel-{}.yml".format(self.kernel_ver_minor))
        self._output_image_path = self._image_path + '.kernel-' + self.kernel_ver_minor
        self._config_path = os.path.abspath(self._args.config)
        self._install_pkg_vm_path =os.path.join(self.install_pkg_vm_path, self._kernel_pkg_name)
        self.chroot_cmd = "chroot {} {}".format(self._mount_path, 
                                                os.path.join(self.qemu_static_path, 
                                                             self.qemu_static_name))
        self.print("image_path: " + self._image_path)
        self.print("kernel_pkg_name: " + self._kernel_pkg_name)
    
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
        cmd = "{} convert -p -O {} {} {}".format(self._qemu_img_path, type, file_in, file_out)
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
            self.unmount(mnt['dst'])
        
    def mount_image(self):
        if not os.path.exists(self._mount_path):
            self.print("creating {}".format(os.path.abspath(self._mount_path)))
            os.mkdir(self._mount_path)
        self.create_loopback()
        # After this point, we have to cleanup before exiting.
        self._image_mounted = True
        self.temp_pkg_path = os.path.abspath(self.install_pkg_path)
        self.print("mount image to {}".format(os.path.abspath(self._mount_path)))
        rc, unused = self.issue_cmd("mount {}p1 {}".format(self.device, self._mount_path))
        self.mount_host_dirs()
        
    def umount_image(self):
        self.umount_host_dirs()
        self.print("umount image from {}".format(self._mount_path))
        self.unmount(self._mount_path)
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
                    self.print("move {} to {}".format(file, dest_path),
                               debug=True)
                    cmd = "mv {} {}".format(file, dest_path)
                    self.issue_cmd(cmd)

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

    def remove_temp_files(self):
        """Remove temp files created by copy_files_to_image"""
        try:
            if os.path.exists(self.temp_pkg_path):
                self.print("cleaning up temp dir: {}".format(self.temp_pkg_path),
                           debug=True)
                shutil.rmtree(self.temp_pkg_path, ignore_errors=True)
        except:
            self.print("Error cleaning up temp dir: {}".format(self.temp_pkg_path))
            traceback.print_exc()

    def copy_kernel_from_image(self):
        kernel_src = "vmlinuz-{}".format(self.kernel_ver)
        kernel_path = os.path.join(self.mount_path, "boot")
        kernel_src_path = os.path.join(kernel_path, kernel_src)
        kernel_dest = "vmlinuz-{}".format(self.kernel_ver_minor)
        kernel_dest_path = os.path.join(self._image_dir_path, kernel_dest)
        cmd = "cp {} {}".format(kernel_src_path, kernel_dest_path)
        self.issue_cmd(cmd)
        initrd_src = "initrd.img-{}".format(self.kernel_ver)
        initrd_path = os.path.join(self.mount_path, "boot")
        initrd_src_path = os.path.join(initrd_path, initrd_src)
        initrd_dest = "initrd.img-{}".format(self.kernel_ver_minor)
        initrd_dest_path = os.path.join(self._image_dir_path, initrd_dest)
        cmd = "cp {} {}".format(initrd_src_path, initrd_dest_path)
        self.issue_cmd(cmd)

    def read_config(self):
        if not os.path.exists(self.vm_config_path):
            print("default config file {} does not exist.  Continuing.")
            return None
        with open(self.vm_config_path) as f:
            self.print("parse {}".format(self.vm_config_path))
            yaml_dict = yaml.safe_load(f)
        if 'qemu-conf' in yaml_dict:
            return yaml_dict
        else:
            return None

    def get_qemu_args_for_kernel(self, existing_args):
        vmlinuz_path = os.path.join(self._image_dir_path,
                                    "vmlinuz-{}".format(self.kernel_ver_minor))
        initrd_path = os.path.join(self._image_dir_path,
                                   "initrd.img-{}".format(self.kernel_ver_minor))
        args = "-kernel {} --initrd {}".format(vmlinuz_path, initrd_path)
        args += ' -append "root=/dev/vda1 nokaslr console=ttyAMA0"'
        return existing_args + " " + args

    def create_config_file(self):
        # Rewrite the config file.
        yaml_dict = self.read_config()
        if yaml_dict == None:
            return;
        if 'qemu_args' not in yaml_dict['qemu-conf']:
            raise Exception("qemu_args not found in {}".format(self.vm_config_path))
        new_args = self.get_qemu_args_for_kernel(yaml_dict['qemu-conf']['qemu_args'])
        yaml_dict['qemu-conf']['qemu_args'] = new_args
        with open(self.kernel_config_path, 'w') as f:
            yaml_dict = yaml.dump(yaml_dict, f)
            self.print("config file {} written".format(self.kernel_config_path))

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
        self.create_config_file()
        self.copy_files_to_image()
        self.umount_image()
        self.run_cmd_in_vm()
        self.mount_image()
        self.copy_kernel_from_image()
        self.remove_temp_files()
        self.umount_image()
        
    def install_kernel_chroot(self):
        self.create_config_file()
        self.copy_qemu_static()
        # modify the share to move old kernels out of the way.
        self.move_old_kernels()
        # install the new kernel.
        self.install_pkg()
        self.copy_kernel_from_image()
        self.remove_temp_files()
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
            print("To start this image run this command:")
            launch_path = os.path.join(self._script_path, "launch_image.py")
            print("python3 {} -p {}".format(launch_path, self._output_image_path))
        except Exception as e:
            sys.stderr.write("Exception hit\n")
            if isinstance(e, SystemExit) and e.code == 0:
                return 0
            traceback.print_exc()
            return 2
        finally:
            self.cleanup()
        
if __name__ == "__main__":
    inst_obj = InstallKernel()    
    inst_obj.run()
