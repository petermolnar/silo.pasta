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
from slugify import slugify
import requests
from requests.auth import HTTPBasicAuth
import arrow
import settings
import keys
import yaml
from pprint import pprint
import feedparser

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
        re.sub(r"^https?://(?:www)?", "", url),
        only_ascii=True,
        lower=True,
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


class Aperture(object):
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": "Bearer %s"
                % (keys.aperture["access_token"])
            }
        )
        self.url = keys.aperture["url"]

    @cached_property
    def channels(self):
        channels = self.session.get(f"{self.url}?action=channels")
        if channels.status_code != requests.codes.ok:
            logging.error(
                "failed to get channels from aperture: ", channels.text
            )
            return None
        try:
            channels = channels.json()
        except ValueError as e:
            logging.error("failed to parse channels from aperture: ", e)
            return None

        if "channels" not in channels:
            logging.error("no channels found in aperture: ")
            return None

        return channels["channels"]

    def channelid(self, channelname):
        for channel in self.channels:
            if channel["name"].lower() == channelname.lower():
                return channel["uid"]
        return None

    def feedmeta(self, url):
        cfile = os.path.join(
            TMPDIR,
            "%s.%s.json" % (url2slug(url), self.__class__.__name__)
        )
        if os.path.exists(cfile):
            with open(cfile, 'rt') as cache:
                return json.loads(cache.read())
        r = {
            'title': url,
            'feed': url,
            'link': url,
            'type': 'rss'
        }
        try:
            feed = feedparser.parse(url)
            if 'feed' in feed:
                for maybe in ['title', 'link']:
                    if maybe in feed['feed']:
                        r[maybe] = feed['feed'][maybe]
        except Exception as e:
            logging.error("feedparser failed on %s: %s" %(url, e))
            r['type']: 'hfeed'
            pass

        with open(cfile, 'wt') as cache:
            cache.write(json.dumps(r))

        return r


    def channelfollows(self, channelid):
        follows = self.session.get(
            f"{self.url}?action=follow&channel={channelid}"
        )
        if follows.status_code != requests.codes.ok:
            logging.error(
                "failed to get follows from aperture: ", follows.text
            )
            return
        try:
            follows = follows.json()
        except ValueError as e:
            logging.error("failed to parse follows from aperture: ", e)
            return

        if "items" not in follows:
            logging.error(
                f"no follows found in aperture for channel {channelid}"
            )
            return

        existing = {}
        for follow in follows["items"]:
            meta = self.feedmeta(follow["url"])
            existing.update({follow["url"]: meta})
        return existing

    @cached_property
    def follows(self):
        follows = {}
        for channel in self.channels:
            follows[channel["name"]] = self.channelfollows(
                channel["uid"]
            )
        return follows

    def export(self):
        opml = etree.Element("opml", version="1.0")
        xmldoc = etree.ElementTree(opml)
        opml.addprevious(
            etree.ProcessingInstruction(
                "xml-stylesheet",
                'type="text/xsl" href="%s"'
                % (settings.opml.get("xsl")),
            )
        )

        head = etree.SubElement(opml, "head")
        title = etree.SubElement(
            head, "title"
        ).text = settings.opml.get("title")
        dt = etree.SubElement(
            head, "dateCreated"
        ).text = arrow.utcnow().format("ddd, DD MMM YYYY HH:mm:ss UTC")
        owner = etree.SubElement(
            head, "ownerName"
        ).text = settings.opml.get("owner")
        email = etree.SubElement(
            head, "ownerEmail"
        ).text = settings.opml.get("email")

        body = etree.SubElement(opml, "body")
        groups = {}
        for group, feeds in self.follows.items():
            if (
                "private" in group.lower()
                or "nsfw" in group.lower()
            ):
                continue

            if group not in groups.keys():
                groups[group] = etree.SubElement(
                    body, "outline", text=group
                )
            for url, meta in feeds.items():
                entry = etree.SubElement(
                    groups[group],
                    "outline",
                    type="rss",
                    text=meta['title'],
                    xmlUrl=meta['feed'],
                    htmlUrl=meta['link']
                )
                etree.tostring(
                    xmldoc,
                    encoding="utf-8",
                    xml_declaration=True,
                    pretty_print=True,
                )
        opmlfile = os.path.join(
            settings.paths.get("content"), "following.opml"
        )
        with open(opmlfile, "wb") as f:
            f.write(
                etree.tostring(
                    xmldoc,
                    encoding="utf-8",
                    xml_declaration=True,
                    pretty_print=True,
                )
            )


class MinifluxFollows(dict):
    def __init__(self):
        self.auth = HTTPBasicAuth(
            keys.miniflux.get("username"), keys.miniflux.get("token")
        )

    @property
    def subscriptions(self):
        feeds = []
        params = {
            "jsonrpc": "2.0",
            "method": "getFeeds",
            "id": keys.miniflux.get("id"),
        }
        r = requests.post(
            keys.miniflux.get("url"),
            data=json.dumps(params),
            auth=self.auth,
        )
        return r.json().get("result", [])

    def sync(self):
        current = []
        for feed in self.subscriptions:
            try:
                current.append(feed["feed_url"])
            except Exception as e:
                logging.error("problem with feed entry: %s", feed)
        for silo, feeds in self.items():
            for feed in feeds:
                xmlurl = feed.get("xmlUrl")
                if len(xmlurl) and xmlurl not in current:
                    logging.info("creating subscription for: %s", feed)
                    params = {
                        "jsonrpc": "2.0",
                        "method": "createFeed",
                        "id": keys.miniflux.get("id"),
                        "params": {"url": xmlurl, "group_name": silo},
                    }
                    r = requests.post(
                        keys.miniflux.get("url"),
                        data=json.dumps(params),
                        auth=self.auth,
                    )

    def export(self):
        opml = etree.Element("opml", version="1.0")
        xmldoc = etree.ElementTree(opml)
        opml.addprevious(
            etree.ProcessingInstruction(
                "xml-stylesheet",
                'type="text/xsl" href="%s"'
                % (settings.opml.get("xsl")),
            )
        )
        head = etree.SubElement(opml, "head")
        title = etree.SubElement(
            head, "title"
        ).text = settings.opml.get("title")
        dt = etree.SubElement(
            head, "dateCreated"
        ).text = arrow.utcnow().format("ddd, DD MMM YYYY HH:mm:ss UTC")
        owner = etree.SubElement(
            head, "ownerName"
        ).text = settings.opml.get("owner")
        email = etree.SubElement(
            head, "ownerEmail"
        ).text = settings.opml.get("email")

        body = etree.SubElement(opml, "body")
        groups = {}
        for feed in self.subscriptions:
            # contains sensitive data, skip it
            if "sessionid" in feed.get(
                "feed_url"
            ) or "sessionid" in feed.get("site_url"):
                continue

            fgroup = feed.get("groups", None)
            if not fgroup:
                fgroup = [{"title": "Unknown", "id": -1}]
            fgroup = fgroup.pop()
            # some groups need to be skipped
            if fgroup["title"].lower() in ["private"]:
                continue
            if fgroup["title"] not in groups.keys():
                groups[fgroup["title"]] = etree.SubElement(
                    body, "outline", text=fgroup["title"]
                )
            entry = etree.SubElement(
                groups[fgroup["title"]],
                "outline",
                type="rss",
                text=feed.get("title"),
                xmlUrl=feed.get("feed_url"),
                htmlUrl=feed.get("site_url"),
            )

        opmlfile = os.path.join(
            settings.paths.get("content"), "following.opml"
        )

        with open(opmlfile, "wb") as f:
            f.write(
                etree.tostring(
                    xmldoc,
                    encoding="utf-8",
                    xml_declaration=True,
                    pretty_print=True,
                )
            )


class Favs(object):
    def __init__(self, silo):
        self.silo = silo
        self.aperture_auth = {
            "Authorization": "Bearer %s"
            % (keys.aperture["access_token"])
        }
        self.aperture_chid = 0

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

    def sync_with_aperture(self):
        channels = requests.get(
            "%s?action=channels" % (keys.aperture["url"]),
            headers=self.aperture_auth,
        )
        if channels.status_code != requests.codes.ok:
            logging.error(
                "failed to get channels from aperture: ", channels.text
            )
            return
        try:
            channels = channels.json()
        except ValueError as e:
            logging.error("failed to parse channels from aperture: ", e)
            return

        if "channels" not in channels:
            logging.error("no channels found in aperture: ")
            return

        for channel in channels["channels"]:
            if channel["name"].lower() == self.silo.lower():
                self.aperture_chid = channel["uid"]
                break

        if not self.aperture_chid:
            logging.error("no channels found for silo ", self.silo)
            return

        follows = requests.get(
            "%s?action=follow&channel=%s"
            % (keys.aperture["url"], self.aperture_chid),
            headers=self.aperture_auth,
        )
        if follows.status_code != requests.codes.ok:
            logging.error(
                "failed to get follows from aperture: ", follows.text
            )
            return
        try:
            follows = follows.json()
        except ValueError as e:
            logging.error("failed to parse follows from aperture: ", e)
            return

        if "items" not in follows:
            logging.error(
                "no follows found in aperture for channel %s (%s)"
                % (self.silo, self.aperture_chid)
            )
            return

        existing = []
        for follow in follows["items"]:
            existing.append(follow["url"])
        existing = list(set(existing))

        for feed in self.feeds:
            if feed["xmlUrl"] not in existing:
                subscribe_to = {
                    "action": "follow",
                    "channel": self.aperture_chid,
                    "url": feed["xmlUrl"],
                }
                logging.info(
                    "subscribing to %s into %s (%s)"
                    % (feed, self.silo, self.aperture_chid)
                )
                subscribe = requests.post(
                    keys.aperture["url"],
                    headers=self.aperture_auth,
                    data=subscribe_to,
                )
                logging.debug(subscribe.text)


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
