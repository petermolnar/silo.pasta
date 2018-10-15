import os
import glob
import pytumblr
import arrow
import keys
import common
import settings
from bleach import clean
from pprint import pprint


class TumblrFavs(common.Favs):
    def __init__(self):
        super().__init__('tumblr')
        self.client = pytumblr.TumblrRestClient(
            keys.tumblr.get('key'),
            keys.tumblr.get('secret'),
            keys.tumblr.get('oauth_token'),
            keys.tumblr.get('oauth_secret')
        )

    def run(self):
        likes = self.client.likes(after=self.since)
        if 'liked_posts' not in likes:
            return

        for like in likes.get('liked_posts'):
            fav = TumblrFav(like)

            fav.run()


class TumblrFav(common.ImgFav):
    def __init__(self, data):
        self.data = data

    def __str__(self):
        return "like-of %s from blog %s" % (self.url, self.blogname)

    @property
    def blogname(self):
        return self.data.get('blog_name')

    @property
    def id(self):
        return self.data.get('id')

    @property
    def url(self):
        return self.data.get('post_url')

    @property
    def content(self):
        return "%s" % self.data.get('caption', '')

    @property
    def title(self):
        title = self.data.get('summary', '')
        if not len(title):
            title = self.data.get('slug', '')
        if not len(title):
            title = common.slugfname(self.url)
        return clean(title.strip())

    @property
    def targetprefix(self):
        return os.path.join(
            settings.paths.get('archive'),
            'favorite',
            "tumblr_%s_%s" % (self.blogname, self.id)
        )

    @property
    def exists(self):
        maybe = glob.glob("%s*" % self.targetprefix)
        if len(maybe):
            return True
        return False

    @property
    def published(self):
        maybe = self.data.get('liked_timestamp', False)
        if not maybe:
            maybe = self.data.get('date', False)
        if not maybe:
            maybe = arrow.utcnow().timestamp
        return arrow.get(maybe)

    @property
    def tags(self):
        return self.data.get('tags', [])

    @property
    def author(self):
        return {
            'name': self.blogname,
            'url': 'http://%s.tumblr.com' % self.blogname
        }

    @property
    def images(self):
        r = {}
        cntr = 0
        for p in self.data.get('photos', []):
            f = "%s-%d%s" % (self.targetprefix, cntr, common.TMPFEXT)
            r.update({
                f: p.get('original_size').get('url')
            })
            cntr = cntr + 1
        return r


    def run(self):
        if not self.exists:
            self.fetch_images()


if __name__ == '__main__':
    t = TumblrFavs()
    t.run()
