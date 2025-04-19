import json, os
import base64
from collections import OrderedDict

# Color codes
cdefault = '\033[0m'
cdefault_bold = '\033[1m'
cred = '\033[91m'
cred_bold = '\033[1;91m'
cyellow = '\033[33m'
cyellow_bold = '\033[1;33m'
cgreen = '\033[32m'
cgreen_bold = '\033[1;32m'
cblue_bold = '\033[1;34m'


def print_error(value, bold:bool = False):
    if bold:
        print(f"{cred_bold}{value}{cdefault}")
    else:
        print(f"{cred}{value}{cdefault}")


def print_warning(value, bold:bool = False):
    if bold:
        print(f"{cyellow_bold}{value}{cdefault}")
    else:
        print(f"{cyellow}{value}{cdefault}")


def print_success(value, bold:bool = False):
    if bold:
        print(f"{cgreen_bold}{value}{cdefault}")
    else:
        print(f"{cgreen}{value}{cdefault}")

def print_info(value:str = "", bold:bool = False, end:str = "\n"):
    if bold:
        print(f"{cdefault_bold}{value}{cdefault}", end=end)
    else:
        print(f"{value}", end=end)
        
def print_header(value):
    print("")
    print(f"{cblue_bold}#################################################################################################################################{cdefault}")
    print(f"{cblue_bold}# {value.center(125)} #{cdefault}")
    print(f"{cblue_bold}#################################################################################################################################{cdefault}")
    

def flatten_dict(d, parent_key=''):
    items = []
    for k, v in d.items():
        full_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, full_key))
        else:
            items.append((full_key, v))
    return items

def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)
    else:
        print(f"Json file not found: {file_path}")