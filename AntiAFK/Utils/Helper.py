import sys
import os

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    else:
        return os.path.join(os.path.abspath("."), relative_path)

def get_res(name):
    if name:
        return get_resource_path(f"Resources\\{name}")

ICON_PATH = get_res("icon.png")

