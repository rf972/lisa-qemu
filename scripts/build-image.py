#
# Copyright 2019 Linaro
#
# Build script for lisa-qemu.
#
# build-image.py --image [qemu image] --config [config yaml]
#
#    [qemu image] is a name of a qemu image.
#                 Available options are those under lisa-qemu/external/qemu/tests/vm 
#                 such as ubuntu.aarch64
#    [config yaml] is a yaml file with format similar to those 
#                  under lisa-qemu/conf
#

import sys
import os
import subprocess
from subprocess import Popen,PIPE
import argparse
from argparse import RawTextHelpFormatter

class build_image:
    qemu_build_path = "external/qemu/build"
    build_image_cmd = "env {} python3 -B ../tests/vm/{} --image {} --force --debug --build-image {}"
    launch_cmd = "env {} python3 -B ../tests/vm/{} --image {} --debug {}"
    default_config_file = "conf/conf_default.yml"
    def __init__(self):
        self.script_path = os.path.dirname(os.path.realpath(__file__))
        self.root_path = os.path.realpath(os.path.join(self.script_path, "../"))
        self.default_config_path = os.path.realpath(os.path.join(self.root_path, 
                                                                 self.default_config_file))
        self.parse_args()
        self.qemu_build_path = os.path.realpath(os.path.join(self.root_path, self.qemu_build_path))
        self.image_name = "{}.img".format(self._args.image_type)
        if self._args.image_path:
            self.image_path = os.path.realpath(self._args.image_path)
        else:
            self.image_path = os.path.join(self.qemu_build_path, self.image_name)
        self.config_path = os.path.realpath(self._args.config)
        self.continue_on_error = self._args.debug
        
    def print(self, trace):
        print("{}: {}".format(sys.argv[0], trace))
            
    def terminate(self, err):
        if not self.continue_on_error:
            exit(err)
            
    def issue_cmd(self, cmd, show_cmd=False, fail_on_err=True, err_msg=None, enable_stdout=True, no_capture=False):
        rc, output = self.run_command(cmd, show_cmd, enable_stdout=enable_stdout, no_capture=no_capture)
        if fail_on_err and rc != 0:
            self.print("cmd failed with status: {} cmd: {}".format(rc, cmd))
            if (err_msg):
                self.print(err_msg)
            self.terminate(1)
        return rc, output
    
    def run_command(self, command, show_cmd=False, enable_stdout=True, no_capture=False):
        output_lines = []
        if show_cmd or self._args.debug:
            print("{}: {} ".format(sys.argv[0], command))
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
                                         description="Build the qemu VM image for use with lisa.",
                                         epilog="examples:\n"\
                                         "  To select all defaults: \n"\
                                         "    build-image.py\n"\
                                         "  Or select one or more arguments\n"\
                                         "    build-image.py -i ubuntu.aarch64 -c conf/config_default.yaml")
        parser.add_argument("--debug", "-D", action="store_true",
                            help="enable debug output")
        parser.add_argument("--dry_run", action="store_true",
                            help="for debugging.  Just show commands to issue.")
        parser.add_argument("--ssh", action="store_true",
                            help="Launch VM and open an ssh shell.")
        parser.add_argument("--image_type", "-i", default="ubuntu.aarch64",
                            help="Type of image to build.\n"\
                            "From external/qemu/tests/vm.\n"\
                            "default is ubuntu.aarch64")
        parser.add_argument("--image_path", "-p", default="",
                            help="Allows overriding path to image.")
        parser.add_argument("--config", "-c", default=self.default_config_path,
                            help="config file.\n"\
                            "default is conf/conf_default.yml.")
        self._args = parser.parse_args()
        
        for arg in ['image_type', 'config']:
            self.print("{}: {}".format(arg, getattr(self._args, arg)))

    def configure_qemu(self):
        cmd = "../configure"
        self.issue_cmd(cmd, show_cmd=True)

    def setup_dirs(self):
        if not os.path.exists(self.qemu_build_path):
            os.mkdir(self.qemu_build_path)
        os.chdir(self.qemu_build_path)

    def build_qemu(self):        
        self.configure_qemu()
        
        cmd = "make -j {}".format(os.cpu_count())        
        self.issue_cmd(cmd, no_capture=True)

    def build_image(self):
        env_vars = "QEMU=./aarch64-softmmu/qemu-system-aarch64 "
        env_vars += "QEMU_CONFIG={} ".format(self.config_path)
        cmd = self.build_image_cmd.format(env_vars, self._args.image_type, self.image_path, self.image_path)
        self.issue_cmd(cmd, no_capture=True)
        print("Image creation successful.")
        print("Image path: {}\n".format(self.image_path))

    def ssh(self):
        env_vars = "QEMU=./aarch64-softmmu/qemu-system-aarch64 "
        env_vars += "QEMU_CONFIG={} ".format(self.config_path)
        cmd = self.launch_cmd.format(env_vars, self._args.image_type, self.image_path, "/bin/bash")
        self.issue_cmd(cmd, no_capture=True)
        
    def run(self):
        self.setup_dirs()
        
        if not self._args.ssh or not os.path.exists(self.image_path):
            # We need to build qemu since we will be using it to run the qemu image.
            self.build_qemu()
        
            # Next we create a qemu image using the image template.
            self.build_image()
            
        if self._args.ssh:
            self.ssh()
        
if __name__ == "__main__":
    inst_obj = build_image()    
    inst_obj.run()
