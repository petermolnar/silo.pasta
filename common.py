import os
import glob
import imghdr
import re
import logging
import shutil
import subprocess
import json
import lxml.etree as etree
from slugify import slugify
import requests
from requests.auth import HTTPBasicAuth
import arrow
import settings
import keys
from pprint import pprint

TMPFEXT = '.xyz'

def slugfname(url):
    return slugify(
        re.sub(r"^https?://(?:www)?", "", url),
        only_ascii=True,
        lower=True
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

class Follows(object):
    def __init__(self):
        self.feeds = {}
        self.auth =  HTTPBasicAuth(
            keys.miniflux.get('username'),
            keys.miniflux.get('token')
        )

    @cached_property
    def active_subscriptions(self):
        feeds = []
        params = {
            'jsonrpc': '2.0',
            'method': 'getFeeds',
            'id': keys.miniflux.get('id')
        }
        r = requests.post(
            keys.miniflux.get('url'),
            data=json.dumps(params),
            auth=self.auth,
        )
        for feed in r.json().get('result', []):
            try:
                feeds.append(feed['feed_url'])
            except Exception as e:
                logging.error('problem with feed entry: %s', feed)
        return feeds

    def syncminiflux(self):
        for silo, feeds in self.feeds.items():
            for f in feeds:
                feed = f.get('xmlUrl')
                if feed not in self.active_subscriptions:
                    params = {
                        'jsonrpc': '2.0',
                        'method': 'createFeed',
                        'id': keys.miniflux.get('id'),
                        'params': {
                            'url': feed,
                            'group_name': silo
                        }
                    }
                    r = requests.post(
                        keys.miniflux.get('url'),
                        data=json.dumps(params),
                        auth=self.auth,
                    )

    def append(self, silo, feeds):
        self.feeds.update({silo: feeds})

    def export(self):
        opml = etree.Element("opml")

        head = etree.SubElement(opml, "head")
        title = etree.SubElement(head, "title").text = "Social media RSS feeds"

        body = etree.SubElement(opml, "body")
        for silo, feeds in self.feeds.items():
            s = etree.SubElement(body, "outline", text=silo)
            for f in feeds:
                entry = etree.SubElement(
                    s,
                    "outline",
                    type="rss",
                    text=f.get('text'),
                    xmlUrl=f.get('xmlUrl'),
                    htmlUrl=f.get('htmlUrl')
                )

        opmlfile = os.path.join(
            settings.paths.get('archive'),
            'feeds.opml'
        )

        with open(opmlfile, 'wb') as f:
            f.write(etree.tostring(opml, pretty_print=True))

class Favs(object):
    def __init__(self, silo):
        self.silo = silo

    @property
    def feeds(self):
        return []

    @property
    def since(self):
        d = os.path.join(
            settings.paths.get('archive'),
            'favorite',
            "%s*" % self.silo
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

    def fetch_images(self):
        for fpath, url in self.images.items():
            self.fetch_image(fpath, url)

    def fetch_image(self, fpath, url):
        logging.info("pulling image %s to %s", url, fpath)
        r = requests.get(url, stream=True)
        if r.status_code == 200:
            with open(fpath, 'wb') as f:
                r.raw.decode_content = True
                shutil.copyfileobj(r.raw, f)

        imgtype = imghdr.what(fpath)
        if not imgtype:
            os.remove(fpath)
            return
        if imgtype in ['jpg', 'jpeg', 'png']:
            self.write_exif(fpath)
        os.rename(fpath, fpath.replace(TMPFEXT, ".%s" % (imgtype)))

    def write_exif(self, fpath):
        logging.info('populating EXIF data of %s' % fpath)

        geo_lat = False
        geo_lon = False

        if hasattr(self, 'geo') and self.geo != None:
            lat, lon = self.geo
            if lat and lon and 'null' != lat and 'null' != lon:
                geo_lat = lat
                geo_lon = lon

        params = [
            'exiftool',
            '-overwrite_original',
            '-XMP:Copyright=Copyright %s %s (%s)' % (
                self.published.to('utc').format('YYYY'),
                self.author.get('name'),
                self.author.get('url'),
            ),
            '-XMP:Source=%s' % self.url,
            '-XMP:ReleaseDate=%s' % self.published.to('utc').format('YYYY:MM:DD HH:mm:ss'),
            '-XMP:Headline=%s' % self.title,
            '-XMP:Description=%s' % self.content,
        ]

        for t in self.tags:
            params.append('-XMP:HierarchicalSubject+=%s' % t)
            params.append('-XMP:Subject+=%s' % t)

        if geo_lat and geo_lon:
            geo_lat = round(float(geo_lat), 6)
            geo_lon = round(float(geo_lon), 6)

            if geo_lat < 0:
                GPSLatitudeRef = 'S'
            else:
                GPSLatitudeRef = 'N'

            if geo_lon < 0:
                GPSLongitudeRef = 'W'
            else:
                GPSLongitudeRef = 'E'

            params.append('-GPSLongitude=%s' % abs(geo_lon))
            params.append('-GPSLatitude=%s' % abs(geo_lat))
            params.append('-GPSLongitudeRef=%s' % GPSLongitudeRef)
            params.append('-GPSLatitudeRef=%s' % GPSLatitudeRef)

        params.append(fpath)

        p = subprocess.Popen(
            params,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, stderr = p.communicate()
        _original = '%s_original' % fpath
        if os.path.exists(_original):
            os.unlink(_original)
