import os
import glob
import json
import logging
import arrow
import requests
import keys
import common
import settings
from time import sleep
from math import ceil
import random
from pprint import pprint


class ASFavs(common.Favs):
    def __init__(self):
        super().__init__("artstation")
        self.user = keys.artstation.get("username")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:69.0) Gecko/20100101 Firefox/69.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            #"DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Pragma": "no-cache",
            "Cache-Control": "max-age=0, no-cache",
        })


session.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:69.0) Gecko/20100101 Firefox/69.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Pragma": "no-cache",
    "Cache-Control": "max-age=0, no-cache",
})

    def paged_likes(self, page=1):
        url = "https://www.artstation.com/users/%s/likes.json?page=%s" % (
            self.user,
            page,
        )
        js = self.session.get(url)
        while js.status_code != requests.codes.ok:
            # FU cloudflare
            pprint(self.session.cookies)
            sleep(round(random.uniform(0.7,3.5), 2))
            js = self.session.get(url)
        try:
            js = js.json()
            if "data" not in js:
                return None
            return js
        except Exception as e:
            logging.error("fetching artstation failed: %s, response: %s", e, js.text)
            return None

    @property
    def likes(self):
        js = self.paged_likes(1)
        if not js:
            return []
        likes = js.get("data", [])
        pages = ceil(js.get("total_count", 1) / 50)
        while pages > 1:
            extras = self.paged_likes(pages)
            if not extras:
                continue
            likes = likes + extras.get("data", [])
            pages = pages - 1
        return likes

    @property
    def feeds(self):
        feeds = []
        url = "https://www.artstation.com/users/%s/following.json" % (self.user)
        js = self.session.get(url, headers=self.headers)
        try:
            js = js.json()
            if "data" not in js:
                logging.error("fetching artstation follows failed: missing data")
                return feeds
            for f in js.get("data"):
                feeds.append(
                    {
                        "text": f.get("username"),
                        "xmlUrl": "https://www.artstation.com/%s.rss"
                        % f.get("subdomain"),
                        "htmlUrl": "https://www.artstation.com/%s" % f.get("subdomain"),
                    }
                )
        except Exception as e:
            logging.error("parsing artstation follows failed: %s", e)
        return feeds

    def run(self):
        # FU cloudflare
        for like in self.likes:
            like = ASLike(like, self.session, self.headers)
            like.run()


class ASLike(common.ImgFav):
    def __init__(self, like, session, headers):
        self.like = like
        self.session = session
        self.headers = headers

    def __str__(self):
        return "like-of %s" % (self.url)

    @property
    def url(self):
        return self.like.get("permalink")

    @property
    def data(self):
        purl = "%s.json" % (self.url.replace("artwork", "projects"))
        data = self.session.get(purl, headers=self.headers)
        try:
            data = data.json()
        except Exception as e:
            logging.error("fetching artstation project %s failed: %s", self.url, e)
            return None
        return data

    @property
    def author(self):
        return {
            "name": self.like.get("user").get("username"),
            "url": self.like.get("user").get("permalink"),
        }

    @property
    def id(self):
        return self.like.get("id")

    @property
    def content(self):
        return "%s" % self.data.get("description_html", "")

    @property
    def title(self):
        title = self.like.get("title")
        if not len(title):
            title = self.like.get("slug")
        if not len(title):
            title = common.url2slug(self.url)
        return title

    @property
    def slug(self):
        maybe = self.like.get("slug")
        if not len(maybe):
            maybe = common.url2slug(self.url)
        return maybe

    @property
    def targetprefix(self):
        return os.path.join(
            settings.paths.get("archive"),
            "favorite",
            "artstation_%s_%s_%s"
            % (
                common.url2slug("%s" % self.like.get("user").get("username")),
                self.like.get("hash_id"),
                self.slug,
            ),
        )

    @property
    def published(self):
        return arrow.get(self.like.get("published_at"))

    @property
    def tags(self):
        t = []
        for c in self.data.get("categories"):
            t.append(c.get("name"))
        return t

    @property
    def images(self):
        r = {}
        cntr = 0
        for img in self.data.get("assets"):
            if img.get("asset_type") != "image":
                logging.debug("skipping asset: %s" % img)
                continue

            f = "%s_%d%s" % (self.targetprefix, cntr, common.TMPFEXT)
            r.update({f: img.get("image_url")})
            cntr = cntr + 1
        return r


if __name__ == "__main__":
    t = ASFavs()
    t.run()
