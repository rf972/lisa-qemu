#
# Copyright 2019 Linaro
#
# Helper script to deprecate old kernels.
#
# move_kernels.py [kernel version]
#
#    [kernel version] is a kernel version such as 5.4.0 or 5.4.0_rc1+
#
import sys
import os
import subprocess
from subprocess import Popen,PIPE
import glob

def move_old_kernels(kernel_version, root_path="/"):
    src_path = os.path.join(root_path, "boot")
    dest_path = os.path.join(src_path, "backup")
    if not os.path.exists(dest_path):
        os.mkdir(dest_path)
    copy_patterns = ['initrd.img*', 'vmlinuz*']
    
    print("move old kernels out of the way.")
    for pattern in copy_patterns:
        for file in glob.glob(os.path.join(src_path, pattern)):
            if (kernel_version not in file):
                print("move {} to {}".format(file, dest_path))
                cmd = "mv {} {}".format(file, dest_path)
                rc = subprocess.call(cmd, shell=True)
                    
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Missing arguments: [kernel version]")
        exit(1)
    move_old_kernels(sys.argv[1])