import os
import glob
import json
import logging
import arrow
import requests
import keys
import common
import settings
from math import ceil
from pprint import pprint

class ASFavs(common.Favs):
    def __init__(self):
        super().__init__('artstation')
        self.user = keys.artstation.get('username')

    def paged_likes(self, page=1):
        url = "https://www.artstation.com/users/%s/likes.json?page=%s" % (
            self.user,
            page
        )
        js = requests.get(url)
        try:
            js = js.json()
            if 'data' not in js:
                return None
            return js
        except Exception as e:
            logging.error('fetching artstation failed: %s', e)
            return None

    @property
    def likes(self):
        js = self.paged_likes()
        if not js:
            return []
        likes = js.get('data', [])
        pages = ceil(js.get('total_count', 1) / 50)
        while pages > 1:
            extras = self.paged_likes()
            if not extras:
                continue
            likes = likes + extras.get('data', [])
            pages = pages - 1
        return likes

    @property
    def feeds(self):
        feeds = []
        js = requests.get(
            "https://www.artstation.com/users/%s/following.json" % self.user
        )
        try:
            js = js.json()
            if 'data' not in js:
                logging.error('fetching artstation follows failed: missing data')
                return feeds
            for f in js.get('data'):
                feeds.append({
                    'text': f.get('username'),
                    'xmlUrl': "https://www.artstation.com/%s.rss" % f.get('subdomain'),
                    'htmlUrl': "https://www.artstation.com/%s" % f.get('subdomain'),
                })
        except Exception as e:
            logging.error('parsing artstation follows failed: %s', e)
        return feeds

    def run(self):
        for like in self.likes:
            like = ASLike(like)
            like.run()


class ASLike(common.ImgFav):
    def __init__(self, like ):
        self.like = like

    def __str__(self):
        return "like-of %s" % (self.url)

    @property
    def url(self):
        return self.like.get('permalink')

    @property
    def data(self):
        purl = "%s.json" % (self.url.replace('artwork', 'projects'))
        data = requests.get(purl)
        try:
            data = data.json()
        except Exception as e:
            logging.error(
                'fetching artstation project %s failed: %s',
                self.url,
                e
            )
            return None
        return data

    @property
    def author(self):
        return {
            'name': self.like.get('user').get('username'),
            'url': self.like.get('user').get('permalink'),
        }

    @property
    def id(self):
        return self.like.get('id')

    @property
    def content(self):
        return '%s' % self.data.get('description_html', '')

    @property
    def title(self):
        title = self.like.get('title')
        if not len(title):
            title = self.like.get('slug')
        if not len(title):
            title = common.slugfname(self.url)
        return title

    @property
    def slug(self):
        maybe = self.like.get('slug')
        if not len(maybe):
            maybe = common.slugfname(self.url)
        return maybe

    @property
    def targetprefix(self):
        return os.path.join(
            settings.paths.get('archive'),
            'favorite',
            "artstation_%s_%s_%s" % (
                common.slugfname('%s' % self.like.get('user').get('username')),
                self.like.get('hash_id'),
                self.slug
            )
        )

    @property
    def exists(self):
        maybe = glob.glob("%s*" % self.targetprefix)
        if len(maybe):
            return True
        return False

    @property
    def published(self):
        return arrow.get(self.like.get('published_at'))

    @property
    def tags(self):
        t = []
        for c in self.data.get('categories'):
            t.append(c.get('name'))
        return t

    @property
    def images(self):
        r = {}
        cntr = 0
        for img in self.data.get('assets'):
            if img.get('asset_type') != 'image':
                logging.debug('skipping asset: %s' % img)
                continue

            f = "%s_%d%s" % (self.targetprefix, cntr, common.TMPFEXT)
            r.update({
                f: img.get('image_url')
            })
            cntr = cntr + 1
        return r

    def run(self):
        if not self.exists:
            self.fetch_images()

if __name__ == '__main__':
    t = ASFavs()
    t.run()
