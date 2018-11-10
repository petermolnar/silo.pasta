import os
import glob
import flickr_api
from bleach import clean
import arrow
import keys
import common
from common import cached_property
import settings
from pprint import pprint
import logging

#class FlickrFollows(common.Follows):


class FlickrFavs(common.Favs):
    def __init__(self):
        super().__init__('flickr')
        flickr_api.set_keys(
            api_key = keys.flickr.get('key'),
            api_secret = keys.flickr.get('secret')
        )
        self.user = flickr_api.Person.findByUserName(
            keys.flickr.get('username')
        )

    @property
    def feeds(self):
        logging.info('Generating OPML feeds for Flickr')
        feeds = []
        pages = 1
        page = 1
        while page <= pages:
            fetched = self.user.getPublicContacts(
                page=page
            )
            for u in fetched:
                feeds.append({
                    'text': u.username,
                    'xmlUrl': "https://api.flickr.com/services/feeds/photos_public.gne?lang=en-us&format=rss_200&id=%s" % u.id,
                    'htmlUrl': "https://www.flickr.com/photos/%s" % u.id
                })
            pages = fetched.info.pages
            page = page + 1
        return feeds

    def run(self):
        pages = 1
        page = 1
        while page <= pages:
            logging.info('fetching for Flickr: page %d' % page)
            fetched = self.user.getFavorites(
                user_id=self.user.id,
                page=page,
                min_fave_date=self.since
            )
            for p in fetched:
                photo = FlickrFav(p)
                photo.run()
            pages = fetched.info.pages
            page = page + 1


class FlickrFav(common.ImgFav):
    def __init__(self, flickrphoto):
        self.flickrphoto = flickrphoto

    def __str__(self):
        return "fav-of %s" % (self.url)

    @cached_property
    def owner(self):
        return self.info.get('owner')

    @cached_property
    def info(self):
        return self.flickrphoto.getInfo()

    @property
    def author(self):
        return {
            'name': "%s" % self.owner.username,
            'url': "%s" % self.owner.getProfileUrl(),
        }

    @property
    def id(self):
        return "%s" % self.info.get('id')

    @property
    def url(self):
        return "https://www.flickr.com/photos/%s/%s/" % (
            self.owner.id,
            self.id
        )

    @property
    def content(self):
        return "%s" % self.info.get('description')

    @property
    def geo(self):
        if 'location' not in self.info:
            return None

        lat = self.info.get('location').get('latitude', None)
        lon = self.info.get('location').get('longitude', None)
        return (lat, lon)

    @property
    def title(self):
        return clean(''.strip("%s" % self.info.get('title')))

    @property
    def targetprefix(self):
        return os.path.join(
            settings.paths.get('archive'),
            'favorite',
            "flickr_%s_%s" % (
                common.slugfname('%s' % self.owner.id),
                self.id,
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
        return arrow.get(self.info.get('dateuploaded'))

    @property
    def tags(self):
        tags = []
        for t in self.info.get('tags'):
            tags.append("%s" % t.text)
        return tags

    @property
    def images(self):
        sizes = self.flickrphoto.getSizes()
        for maybe in ['Original', 'Large 2048', 'Large 1600', 'Large', 'Medium']:
            if maybe in sizes:
                f = "%s%s" % (self.targetprefix, common.TMPFEXT)
                return {
                    f: sizes.get(maybe).get('source')
                }

    def run(self):
        if not self.exists:
            self.fetch_images()


if __name__ == '__main__':
    t = FlickrFavs()
    t.run()
