#
# Copyright 2019 Linaro
#
# Base class for our command objects.
#

import sys
import os
import stat
import shutil
import subprocess
from subprocess import Popen,PIPE
import argparse
import yaml

class BaseCmd:
    
    def __init__(self):
        self.kernel_ver = None
        self.kernel_ver_minor = None
        self._debug = False
        self._dry_run = False

    def set_debug(self, debug):
        self._debug = debug

    def set_dry_run(self, dry_run):
        self._dry_run = dry_run

    def print(self, trace, debug=False):
        if not debug or self._debug:
            print("{}: {}".format(sys.argv[0], trace))
            
    def terminate(self, err):
        if not self.continue_on_error:
            exit(err)
            
    def issue_cmd(self, cmd, show_cmd=False, fail_on_err=True, 
                  err_msg=None, enable_stdout=True, no_capture=False):
        rc, output = self.run_command(cmd, show_cmd, enable_stdout=enable_stdout, no_capture=no_capture)
        if fail_on_err and rc != 0:
            self.print("cmd failed with status: {} cmd: {}".format(rc, cmd))
            if (err_msg):
                self.print(err_msg)
            self.terminate(1)
        return rc, output
    
    def run_command(self, command, show_cmd=False, enable_stdout=True, no_capture=False):
        output_lines = []
        if show_cmd or self._debug:
            print("{}: {} ".format(sys.argv[0], command))
        if self._dry_run:
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

    def get_kernel_img_version(self, image):
        if self.kernel_ver:
            return
        entries = image.split("-")
        if len(entries) > 2:
            self.kernel_ver_minor = "{}-{}".format(entries[1], entries[2])
            self.kernel_ver = entries[1]
        if self.kernel_ver == None:
            raise Exception("Unable to determine kernel version, "\
                            "please use --kernel_ver argument.")
        self.print("Kernel version is:"\
                   " {} ({})".format(self.kernel_ver, self.kernel_ver_minor),                   
                   debug=True)

    def get_kernel_pkg_version(self, kernel_pkg_path):
        if self.kernel_ver:
            return
        cmd = "dpkg --info {}".format(kernel_pkg_path)
        rc, output = self.issue_cmd(cmd)
        for line in output:
            if "Version: " in line:
                entries = line.split(" ")
                if len(entries) > 2:
                    self.kernel_ver_minor = entries[2].rstrip()
                    self.kernel_ver = entries[2].split("-")[0].rstrip()
        if self.kernel_ver == None:
            raise Exception("Unable to determine kernel version, "\
                            "please use --kernel_ver argument.")
        self.print("Kernel version is:"\
                   " {} ({})".format(self.kernel_ver, self.kernel_ver_minor),debug=True)