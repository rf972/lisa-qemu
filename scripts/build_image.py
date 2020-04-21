#
# Copyright 2019 Linaro
#
# Build script for lisa-qemu.
#
# build_image.py --image [qemu image] --config [config yaml]
#
#    [qemu image] is a name of a qemu image.
#                 Available options are those under lisa-qemu/external/qemu/tests/vm 
#                 such as ubuntu.aarch64
#    [config yaml] is a yaml file with format similar to those 
#                  under lisa-qemu/conf
#

import sys
import os
import stat
import shutil
import subprocess
from subprocess import Popen,PIPE
import argparse
from argparse import RawTextHelpFormatter
import yaml
import base_cmd

class BuildImage(base_cmd.BaseCmd):
    qemu_path_rel = "external/qemu"
    qemu_build_path_rel = "external/qemu/build"
    build_path_rel = "build"
    def_key_path_rel = "default-keys"
    build_image_cmd = "env {} python3 -B ../tests/vm/{} --image {} --force {} --build-image {}"
    launch_cmd = "env {} python3 -B ../tests/vm/{} --image {} {} {}"
    default_config_file = "conf/conf_default.yml"
    qemu_key_path_rel = "tests/keys"
    key_files = ["id_rsa", "id_rsa.pub"]
    
    def __init__(self, ssh=False):
        super(BuildImage, self).__init__()
        self.script_path = os.path.dirname(os.path.realpath(__file__))
        self.root_path = os.path.realpath(os.path.join(self.script_path, "../"))
        self.orig_default_config_path = os.path.realpath(os.path.join(self.root_path, 
                                                         self.default_config_file))
        if 'QEMU_CONFIG' in os.environ:
            self.default_config_path = os.environ['QEMU_CONFIG']
            if not os.path.isabs(self.default_config_path):
                self.default_config_path = os.path.realpath(os.path.join(self.root_path, 
                                                                         self.default_config_path))
        else:
            self.default_config_path = self.orig_default_config_path
        self.qemu_path = os.path.join(self.root_path, self.qemu_path_rel)
        self.test_vm_path = os.path.join(self.qemu_path, "tests/vm")
        self.parse_args()
        self.set_debug(self._args.debug)
        self.set_dry_run(self._args.dry_run)
        self.build_path = os.path.realpath(os.path.join(self.root_path, self.build_path_rel))
        self.qemu_build_path = os.path.realpath(os.path.join(self.root_path, 
                                                             self.qemu_build_path_rel))
        self.image_name = "{}.img".format(self._args.image_type)
        self.lisa_name = "VM-" + self._args.image_type
        self.image_dir_path = os.path.join(self.build_path, self.lisa_name)
        self.lisa_config_path = os.path.join(self.build_path, "current_vm_config.yml")
        if self._args.image_path:
            self.image_path = os.path.realpath(self._args.image_path)
        else:
            self.image_path = os.path.join(self.image_dir_path, self.image_name)
        self.def_key_path = os.path.join(self.build_path, self.def_key_path_rel)
        self.qemu_key_path = os.path.join(self.qemu_path, self.qemu_key_path_rel)
        self.config_path = os.path.realpath(self._args.config)
        self.print("config file: {}".format(self.config_path), debug=True)
        self.continue_on_error = self._args.debug
        self.vm_config_path = os.path.join(self.image_dir_path, "conf.yml")
        image_name = os.path.basename(self.image_path)
        if ".kernel-" in image_name:
            self.get_kernel_img_version(image_name)
            kernel_config_file = os.path.join(self.image_dir_path, 
                         "conf-kernel-{}.yml".format(self.kernel_ver_minor))
            if os.path.exists(kernel_config_file):
                self.print("using kernel config: {}".format(kernel_config_file),
                           debug=True)
                self.vm_config_path = kernel_config_file
                
        self.src_ssh_key = os.path.join(self.def_key_path, "id_rsa")
        self.dest_ssh_key = os.path.join(self.image_dir_path, "id_rsa")
        self.src_ssh_pub_key = os.path.join(self.def_key_path, "id_rsa.pub")
        self.dest_ssh_pub_key = os.path.join(self.image_dir_path, "id_rsa.pub")
        self.ssh_port = 0
        self.start_ssh = (ssh or self._args.ssh)
        self.building_image = not os.path.exists(self.image_path)
        
        # If we are doing a launch, and we are not building the image
        # then point the config to use to either the default (vm_config_path)
        # or the config provided by the user.
        # Normally the config is parsed and generated, 
        # to convert relative paths to absolute, but
        # in this case we assume the user provided absolute paths.
        if self.start_ssh and not self.building_image and \
           self._args.config != self.orig_default_config_path:
            self.vm_config_path = self._args.config

    def get_image_types(self, per_line = 3, 
                        separator = "\n                   "):
        bytes = subprocess.check_output("grep --exclude=Make* "\
                               "--exclude=aarch64* --exclude=basevm* "\
                               "-l python3 {}/*".format(self.test_vm_path), shell=True)
        types = bytes.decode().replace(self.test_vm_path + "/", "")
        types_list = types.split()
        types_str = ""
        index = 0
        for image in types_list:
            types_str += image + " "
            index += 1
            if index >= per_line:
                types_str += separator
                index = 0
        return types_str
    
    def parse_args(self):
        image_types = self.get_image_types()
        parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter,
                                         description="Build the qemu VM image for use with lisa.",
                                         epilog="examples:\n"\
                                         "  To select all defaults: \n"\
                                         "   "+ sys.argv[0] +"\n"\
                                         "  Or select one or more arguments\n"\
                                         "    {} --image_type ubuntu.aarch64 "\
                                         "--config conf/conf_default.yml\n".format(sys.argv[0]) +
                                         "\nvalid image types: {}".format(image_types))
        parser.add_argument("--debug", action="store_true",
                            help="enable debug output")
        parser.add_argument("--dry_run", action="store_true",
                            help="Just show commands issued by script, do not execute them.")
        parser.add_argument("--ssh", action="store_true",
                            help="Launch VM and open an ssh shell.")
        parser.add_argument("--image_type", default="ubuntu.aarch64",
                            help="Type of image to build.\n"\
                            "From external/qemu/tests/vm.\n"\
                            "default is ubuntu.aarch64")
        parser.add_argument("--image_path", default="",
                            help="Allows overriding path to image.")
        parser.add_argument("--config", default=self.default_config_path,
                            help="config file.\n"\
                            "default is conf/conf_default.yml.")
        parser.add_argument("--build_qemu", action="store_true",
                            help="Build QEMU. QEMU is built initially and not repeated\n"\
                                 "unless this argument is selected.")
        self._args = parser.parse_args()
        
    def configure_qemu(self):
        cmd = "../configure"
        self.issue_cmd(cmd, show_cmd=True)
        
    def create_dir(self, dir):
        if not os.path.exists(dir):
            self.print("Create {}".format(dir), debug=True)
            os.mkdir(dir)

    def setup_dirs(self):
        self.create_dir(self.qemu_build_path)
        self.create_dir(self.build_path)
        self.create_dir(self.image_dir_path)
        os.chdir(self.qemu_build_path)
        
    def create_default_keys(self):
        self.create_dir(self.def_key_path)
        for file in self.key_files:
            src_file = os.path.join(self.qemu_key_path, file)
            dst_file = os.path.join(self.def_key_path, file)
            self.print("copy {} -> {}".format(src_file, dst_file), 
                   debug=True)
            shutil.copy(src_file, dst_file)
            os.chmod(dst_file, stat.S_IRUSR | stat.S_IWUSR)
        
    def copy_key_files(self):
        self.print("copy {} -> {}".format(self.src_ssh_key, self.dest_ssh_key), 
                   debug=True)
        shutil.copy(self.src_ssh_key, self.dest_ssh_key)
        self.print("copy {} -> {}".format(self.src_ssh_pub_key, self.dest_ssh_pub_key), 
                   debug=True)
        shutil.copy(self.src_ssh_pub_key, self.dest_ssh_pub_key)

    def modify_path(self, path):
        if not os.path.isabs(path):
            path = os.path.realpath(os.path.join(self.root_path, path))
        return path

    def parse_config_file(self, config_file):
        # Create the config file by parsing the input file and
        # adding any needed defaults. 
        if not os.path.exists(config_file):
            raise Exception("config file {} does not exist".format(config_file))
        with open(config_file) as f:
            self.print("parse {}".format(config_file), debug=True)
            yaml_dict = yaml.safe_load(f)
            
        if 'qemu-conf' in yaml_dict:
            target_dict = yaml_dict['qemu-conf']
            if 'ssh_key' in target_dict:
                target_dict['ssh_key'] = self.modify_path(target_dict['ssh_key'])
                self.src_ssh_key = target_dict['ssh_key']
                #self.dest_ssh_key = target_dict['ssh_key']
            else:
                target_dict['ssh_key'] = self.dest_ssh_key
            self.print("src_ssh_key: {}".format(self.src_ssh_key),debug=True)
            self.print("dest_ssh_key: {}".format(self.dest_ssh_key),debug=True)
            if 'ssh_pub_key' in target_dict:
                target_dict['ssh_pub_key'] = self.modify_path(target_dict['ssh_pub_key'])
                self.src_ssh_pub_key = target_dict['ssh_pub_key']
                #self.dest_ssh_pub_key = target_dict['ssh_pub_key']
            else:
                target_dict['ssh_pub_key'] = self.dest_ssh_pub_key
            self.print("src_ssh_pub_key: {}".format(self.src_ssh_pub_key),debug=True)
            self.print("dest_ssh_pub_key: {}".format(self.dest_ssh_pub_key),debug=True)
            if 'ssh_port' in target_dict:
                self.ssh_port = target_dict['ssh_port']
        else:
            raise Exception("config file {} format is invalid.".format(config_file))
        self.yaml_dict = yaml_dict

    def create_config_file(self):
        # Rewrite the config file.
        with open(self.vm_config_path, 'w') as f:
            yaml_dict = yaml.dump(self.yaml_dict, f)
            self.print("config file {} written".format(self.vm_config_path), debug=True)

    def write_current_config(self):
        # Write down the current config file.  
        # This will be used by lisa
        yaml_dict = {'kind'     : "linux",
                     'name'     : self.lisa_name,
                     'host'     : "127.0.0.1",
                     'username' : "root",
                     'keyfile'  : self.dest_ssh_key,
                     'port'     : self.ssh_port,
                     }
        with open(self.lisa_config_path, 'w') as f:
            yaml_dict = yaml.dump(yaml_dict, f)
            self.print("current config {} written".format(self.lisa_config_path), debug=True)

    def build_qemu(self):
        print("configuring QEMU.   Please be patient, this may take several minutes...")
        self.configure_qemu()
        print("QEMU configure complete.")
        
        print("building QEMU.   Please be patient, this may take several minutes...")
        cmd = "make -j {}".format(os.cpu_count())        
        self.issue_cmd(cmd, no_capture=True)
        print("QEMU build complete")

    def build_image(self):
        args = "--build-path {} ".format(self.qemu_build_path)
        env_vars = "QEMU_LOCAL=1 "
        env_vars += "QEMU_CONFIG={} ".format(self.vm_config_path)
        if self._args.debug:
            args += "--debug"
        print("\n")
        print("Image creation starting.  Please be patient, this may take several minutes...")
        print("To enable more verbose tracing of each step, please use the --debug option.\n")
        cmd = self.build_image_cmd.format(env_vars, 
                                          self._args.image_type, 
                                          self.image_path, 
                                          args,
                                          self.image_path)
        rc, output = self.issue_cmd(cmd, no_capture=True)
        if rc != 0:
            print("Image creation failed.")
        else:
            print("Image creation successful.")
            print("Image path: {}\n".format(self.image_path))

    def ssh(self):
        print("Conf:        {}".format(self.vm_config_path))
        print("Image type:  {}".format(self._args.image_type))
        print("Image path:  {}\n".format(self.image_path))
        args = "--build-path {} ".format(self.qemu_build_path)
        env_vars = "QEMU_LOCAL=1 "
        env_vars += "QEMU_CONFIG={} ".format(self.vm_config_path)
        if self._args.debug:
            args += "--debug"
        print("Launching Image.  Please be patient, this may take several minutes...")
        print("To enable more verbose tracing of each step, please use the --debug option.\n")
        cmd = self.launch_cmd.format(env_vars, self._args.image_type, self.image_path, args, "/bin/bash")
        self.issue_cmd(cmd, no_capture=True)
        
    def run(self):
        self.require_build = not os.path.exists(self.qemu_build_path)
        self.setup_dirs()
        
        if not self.start_ssh or not os.path.exists(self.image_path):
            self.print("Start image file generation.", debug=True)
            self.parse_config_file(self.config_path)
            self.create_default_keys()
            self.create_config_file()
            self.copy_key_files()
            
            if self.require_build or self._args.build_qemu:
                # We need to build qemu since we will be using it to run the qemu image.
                self.build_qemu()
        
            # Next we create a qemu image using the image template.
            self.build_image()
        else:
            self.print("skip image file generation, already exists.", debug=True)
            
        if self.start_ssh:
            self.parse_config_file(self.vm_config_path)
            self.write_current_config()
            self.ssh()
        
if __name__ == "__main__":
    inst_obj = BuildImage()    
    inst_obj.run()
