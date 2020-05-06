import os
import re
import argparse
import logging

class nameddict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

base = os.path.abspath(os.path.expanduser("~/Projects/petermolnar.net"))

opml = nameddict({
    "owner": "Peter Molnar",
    "email": "mail@petermolnar.net",
    "title": "feeds followed by petermolnar.net",
    "xsl": "https://petermolnar.net/following.xsl",
})

paths = nameddict({
    "archive": os.path.join(base, "archive"),
    "content": os.path.join(base, "content"),
    "bookmarks": os.path.join(base, "archive", "bookmarks")
})

loglevels = {"critical": 50, "error": 40, "warning": 30, "info": 20, "debug": 10}

_parser = argparse.ArgumentParser(description="Parameters for silo.pasta")
_parser.add_argument("--loglevel", default="debug", help="change loglevel")

args = vars(_parser.parse_args())
logging.basicConfig(
    level=loglevels[args.get("loglevel")],
    format="%(asctime)s - %(levelname)s - %(message)s",
)
