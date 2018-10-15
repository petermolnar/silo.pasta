import os
import glob
import imghdr
import re
import logging
import shutil
import subprocess
from slugify import slugify
import requests
import arrow
import settings
from pprint import pprint

TMPFEXT = '.xyz'

def slugfname(url):
    return slugify(
        re.sub(r"^https?://(?:www)?", "", url),
        only_ascii=True,
        lower=True
    )[:200]


class Favs(object):
    def __init__(self, silo):
        self.silo = silo

    @property
    def since(self):
        mtime = 0
        d = os.path.join(
            settings.paths.get('archive'),
            'favorite',
            "%s-*" % self.silo
        )
        files = glob.glob(d)

        if (len(files)):
            for f in files:
                ftime = int(os.path.getmtime(f))
                if ftime > mtime:
                    mtime = ftime
        # TODO why is this here?
        mtime = mtime + 1
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
