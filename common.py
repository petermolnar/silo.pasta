import os
import glob
import imghdr
import re
import logging
import shutil
import subprocess
import json
from io import BytesIO
import lxml.etree as etree
import requests
from requests.auth import HTTPBasicAuth
import arrow
import settings
import keys
import yaml
from pprint import pprint
import feedparser

# https://www.peterbe.com/plog/fastest-python-function-to-slugify-a-string
NON_URL_SAFE = [
    '"',
    "#",
    "$",
    "%",
    "&",
    "+",
    ",",
    "/",
    ":",
    ";",
    "=",
    "?",
    "@",
    "[",
    "]",
    "^",
    "`",
    "{",
    "|",
    "}",
    "~",
    "'",
    ".",
    "\\",
]
# TRANSLATE_TABLE = {ord(char): "" for char in NON_URL_SAFE}
RE_NON_URL_SAFE = re.compile(
    r"[{}]".format("".join(re.escape(x) for x in NON_URL_SAFE))
)
RE_REMOVESCHEME = re.compile(r"^https?://(?:www)?")


def slugify(text):
    text = RE_REMOVESCHEME.sub("", text).strip()
    text = RE_NON_URL_SAFE.sub("", text).strip()
    text = text.lower()
    text = "_".join(re.split(r"\s+", text))
    return text



TMPFEXT = ".xyz"
MDFEXT = ".md"

TMPSUBDIR = "nasg"
SHM = "/dev/shm"

if os.path.isdir(SHM) and os.access(SHM, os.W_OK):
    TMPDIR = f"{SHM}/{TMPSUBDIR}"
else:
    TMPDIR = os.path.join(gettempdir(), TMPSUBDIR)

if not os.path.isdir(TMPDIR):
    os.makedirs(TMPDIR)


def utfyamldump(data):
    """ dump YAML with actual UTF-8 chars """
    return yaml.dump(
        data, default_flow_style=False, indent=4, allow_unicode=True
    )


def url2slug(url):
    return slugify(
        re.sub(r"^https?://(?:www)?", "", url)
        #only_ascii=True,
        #lower=True,
    )[:200]


class cached_property(object):
    """ extermely simple cached_property decorator:
    whenever something is called as @cached_property, on first run, the
    result is calculated, then the class method is overwritten to be
    a property, contaning the result from the method
    """

    def __init__(self, method, name=None):
        self.method = method
        self.name = name or method.__name__

    def __get__(self, inst, cls):
        if inst is None:
            return self
        result = self.method(inst)
        setattr(inst, self.name, result)
        return result


class Favs(object):
    def __init__(self, silo):
        self.silo = silo

    @property
    def feeds(self):
        return []

    @property
    def since(self):
        d = os.path.join(
            settings.paths.get("archive"), "favorite", "%s*" % self.silo
        )
        files = glob.glob(d)
        if len(files):
            mtime = max([int(os.path.getmtime(f)) for f in files])
        else:
            mtime = 0
        return mtime


class ImgFav(object):
    def __init__(self):
        return

    def run(self):
        if not self.exists:
            self.fetch_images()
            self.save_txt()

    @property
    def exists(self):
        maybe = glob.glob("%s*" % self.targetprefix)
        if len(maybe):
            return True
        return False

    def save_txt(self):
        attachments = [
            os.path.basename(fn)
            for fn in glob.glob("%s*" % self.targetprefix)
            if not os.path.basename(fn).endswith(".md")
        ]
        meta = {
            "title": self.title,
            "favorite-of": self.url,
            "date": str(self.published),
            "sources": list(self.images.values()),
            "attachments": attachments,
            "author": self.author,
        }
        r = "---\n%s\n---\n\n" % (utfyamldump(meta))
        with open("%s%s" % (self.targetprefix, MDFEXT), "wt") as fpath:
            fpath.write(r)

    def fetch_images(self):
        for fpath, url in self.images.items():
            self.fetch_image(fpath, url)

    def fetch_image(self, fpath, url):
        logging.info("pulling image %s to %s", url, fpath)
        r = requests.get(url, stream=True)
        if r.status_code == 200:
            with open(fpath, "wb") as f:
                r.raw.decode_content = True
                shutil.copyfileobj(r.raw, f)

        imgtype = imghdr.what(fpath)
        if not imgtype:
            os.remove(fpath)
            return
        if imgtype in ["jpg", "jpeg", "png"]:
            self.write_exif(fpath)
        os.rename(fpath, fpath.replace(TMPFEXT, ".%s" % (imgtype)))

    def write_exif(self, fpath):
        logging.info("populating EXIF data of %s" % fpath)

        geo_lat = False
        geo_lon = False

        if hasattr(self, "geo") and self.geo != None:
            lat, lon = self.geo
            if lat and lon and "null" != lat and "null" != lon:
                geo_lat = lat
                geo_lon = lon

        params = [
            "exiftool",
            "-overwrite_original",
            "-XMP:Copyright=Copyright %s %s (%s)"
            % (
                self.published.to("utc").format("YYYY"),
                self.author.get("name"),
                self.author.get("url"),
            ),
            "-XMP:Source=%s" % self.url,
            "-XMP:ReleaseDate=%s"
            % self.published.to("utc").format("YYYY:MM:DD HH:mm:ss"),
            "-XMP:Headline=%s" % self.title,
            "-XMP:Description=%s" % self.content,
        ]

        for t in self.tags:
            params.append("-XMP:HierarchicalSubject+=%s" % t)
            params.append("-XMP:Subject+=%s" % t)

        if geo_lat and geo_lon:
            geo_lat = round(float(geo_lat), 6)
            geo_lon = round(float(geo_lon), 6)

            if geo_lat < 0:
                GPSLatitudeRef = "S"
            else:
                GPSLatitudeRef = "N"

            if geo_lon < 0:
                GPSLongitudeRef = "W"
            else:
                GPSLongitudeRef = "E"

            params.append("-GPSLongitude=%s" % abs(geo_lon))
            params.append("-GPSLatitude=%s" % abs(geo_lat))
            params.append("-GPSLongitudeRef=%s" % GPSLongitudeRef)
            params.append("-GPSLatitudeRef=%s" % GPSLatitudeRef)

        params.append(fpath)

        p = subprocess.Popen(
            params,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, stderr = p.communicate()
        _original = "%s_original" % fpath
        if os.path.exists(_original):
            os.unlink(_original)
