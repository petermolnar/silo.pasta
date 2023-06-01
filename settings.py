import os
import re
import argparse
import logging

class nameddict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

paths = nameddict({
    "archive": os.path.join(os.path.expanduser('~'), "archiv"),
})

loglevels = {"critical": 50, "error": 40, "warning": 30, "info": 20, "debug": 10}

_parser = argparse.ArgumentParser(description="Parameters for silo.pasta")
_parser.add_argument("--loglevel", default="debug", help="change loglevel")

args = vars(_parser.parse_args())
logging.basicConfig(
    level=loglevels[args.get("loglevel")],
    format="%(asctime)s - %(levelname)s - %(message)s",
)
