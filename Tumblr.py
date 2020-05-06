import os
import glob
import logging
import pytumblr
import arrow
import keys
import common
import settings
from bleach import clean
from pprint import pprint


class TumblrFavs(common.Favs):
    def __init__(self):
        super().__init__("tumblr")
        self.client = pytumblr.TumblrRestClient(
            keys.tumblr.get("key"),
            keys.tumblr.get("secret"),
            keys.tumblr.get("oauth_token"),
            keys.tumblr.get("oauth_secret"),
        )

    @property
    def feeds(self):
        logging.info("Generating OPML feeds for Tumblr")
        feeds = []
        offset = 0
        has_more = True
        while has_more:
            fetched = self.client.following(offset=offset)
            if "_links" in fetched and "next" in fetched["_links"] and len(fetched):
                offset = (
                    fetched.get("_links").get("next").get("query_params").get("offset")
                )
            else:
                has_more = False

            for u in fetched.get("blogs"):
                feeds.append(
                    {
                        "text": u.get("name"),
                        "xmlUrl": "https://cloud.petermolnar.net/rss-bridge/index.php?action=display&bridge=Tumblr&searchUsername=%s&format=Atom" % u.get("name"),
                        #"xmlUrl": "%srss" % u.get("url"),
                        "htmlUrl": u.get("url"),
                    }
                )
        return feeds

    def run(self):
        has_more = True
        after = self.since
        while has_more:
            logging.info("fetching for Tumblr: after %d" % after)
            fetched = self.client.likes(after=after)
            if "liked_posts" not in fetched:
                has_more = False
            elif "_links" in fetched and "prev" in fetched["_links"] and len(fetched):
                after = (
                    fetched.get("_links").get("prev").get("query_params").get("after")
                )
                after = int(after)
            else:
                has_more = False

            for like in fetched.get("liked_posts"):
                fav = TumblrFav(like)
                fav.run()


class TumblrFav(common.ImgFav):
    def __init__(self, data):
        self.data = data

    def __str__(self):
        return "like-of %s from blog %s" % (self.url, self.blogname)

    @property
    def blogname(self):
        return self.data.get("blog_name")

    @property
    def id(self):
        return self.data.get("id")

    @property
    def url(self):
        return self.data.get("post_url")

    @property
    def content(self):
        return "%s" % self.data.get("caption", "")

    @property
    def title(self):
        title = self.data.get("summary", "")
        if not len(title):
            title = self.data.get("slug", "")
        if not len(title):
            title = common.url2slug(self.url)
        return clean(title.strip())

    @property
    def targetprefix(self):
        return os.path.join(
            settings.paths.get("archive"),
            "favorite",
            "tumblr_%s_%s" % (self.blogname, self.id),
        )

    @property
    def published(self):
        maybe = self.data.get("liked_timestamp", False)
        if not maybe:
            maybe = self.data.get("date", False)
        if not maybe:
            maybe = arrow.utcnow().timestamp
        return arrow.get(maybe)

    @property
    def tags(self):
        return self.data.get("tags", [])

    @property
    def author(self):
        return {"name": self.blogname, "url": "http://%s.tumblr.com" % self.blogname}

    @property
    def images(self):
        r = {}
        cntr = 0
        for p in self.data.get("photos", []):
            f = "%s_%d%s" % (self.targetprefix, cntr, common.TMPFEXT)
            r.update({f: p.get("original_size").get("url")})
            cntr = cntr + 1
        return r


if __name__ == "__main__":
    t = TumblrFavs()
    t.run()
