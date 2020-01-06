#
# Copyright 2020 Linaro
#
# Launches an image created via build_image.py.
#
import build_image

if __name__ == "__main__":
    inst_obj = build_image.build_image(ssh=True)    
    inst_obj.run()