import os
import re
import argparse
import logging

base = os.path.abspath(os.path.expanduser('~/Projects/petermolnar.net'))

opml = {
    'owner': 'Peter Molnar',
    'email': 'mail@petermolnar.net',
    'title': 'feeds followed by petermolnar.net',
    'xsl': 'https://petermolnar.net/following.xsl'
}

paths = {
    'archive': os.path.join(base, 'archive'),
    'content': os.path.join(base, 'content'),
}

loglevels = {
    'critical': 50,
    'error': 40,
    'warning': 30,
    'info': 20,
    'debug': 10
}

_parser = argparse.ArgumentParser(description='Parameters for silo.pasta')
_parser.add_argument(
    '--loglevel',
    default='info',
    help='change loglevel'
)

args = vars(_parser.parse_args())
logging.basicConfig(
    level=loglevels[args.get('loglevel')],
    format='%(asctime)s - %(levelname)s - %(message)s'
)
