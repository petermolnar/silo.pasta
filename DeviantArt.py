import os
import glob
import deviantart
from bleach import clean
import arrow
import keys
import common
import settings
from pprint import pprint
import logging

class DAFavs(common.Favs):
    def __init__(self):
        super().__init__('deviantart')
        self.client = deviantart.Api(
            keys.deviantart.get('key'),
            keys.deviantart.get('secret'),
            scope='user'
        )
        self.favfolder = None

    @property
    def feeds(self):
        logging.info('Generating OPML feeds for DeviantArt')
        feeds = []
        offset = 0
        has_more = True
        while has_more:
            logging.info('Generating OPML feeds for DeviantArt: offset %d' % offset)
            try:
                following = self.client.get_friends(
                    username=keys.deviantart.get('username'),
                    offset=offset
                )
                offset = following.get('next_offset')
                for follow in following.get('results'):
                    u = follow.get('user').username.lower()
                    feeds.append({
                        'text': u,
                        'xmlUrl': "https://backend.deviantart.com/rss.xml?q=gallery%%3A%s" % u,
                        'htmlUrl': "https://www.deviantart.com/%s" % u
                    })
                has_more = following.get('has_more')
            except deviantart.api.DeviantartError as e:
                print(e)
                break
        return feeds

    def run(self):
        offset = 0
        while not self.favfolder:
            logging.info('fetching for DeviantArt: offset %d' % offset)
            try:
                folders = self.client.get_collections(
                    username=keys.deviantart.get('username'),
                    offset=offset
                )
                offset = folders.get('next_offset')
                for r in folders.get('results'):
                    if r.get('name') == 'Featured':
                        self.favfolder = r.get('folderid')
                if (folders.get('has_more') == False):
                    break
            except deviantart.api.DeviantartError as e:
                print(e)
                break

        offset = 0
        has_more = True
        while has_more:
            try:
                fetched = self.client.get_collection(
                    self.favfolder,
                    username=keys.deviantart.get('username'),
                    offset=offset,
                )
                for r in fetched.get('results'):
                    fav = DAFav(r)
                    fav.run()
                offset = fetched.get('next_offset')
                has_more = fetched.get('has_more')
                if (has_more == False):
                    break
            except deviantart.api.DeviantartError as e:
                print(e)
                break


class DAFav(common.ImgFav):
    def __init__(self, deviation, ):
        self.deviation = deviation

    def __str__(self):
        return "fav-of %s" % (self.deviation.url)

    @property
    def author(self):
        return {
            'name': self.deviation.author,
            'url': 'http://%s.deviantart.com' % self.deviation.author
        }

    @property
    def id(self):
        return self.deviation.deviationid

    @property
    def url(self):
        return self.deviation.url

    @property
    def content(self):
        if self.deviation.excerpt:
            return "%s" % self.deviation.excerpt
        return ''

    @property
    def title(self):
        title = self.deviation.title
        if not len(title):
            title = common.slugfname(self.url)
        return clean(title.strip())

    @property
    def targetprefix(self):
        return os.path.join(
            settings.paths.get('archive'),
            'favorite',
            "deviantart_%s_%s_%s" % (
                common.slugfname('%s' % self.deviation.author),
                self.id,
                common.slugfname('%s' % self.title)
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
        return arrow.get(self.deviation.published_time)

    @property
    def tags(self):
        return [self.deviation.category]

    @property
    def images(self):
        f = "%s%s" % (self.targetprefix, common.TMPFEXT)
        return {
            f: self.deviation.content.get('src')
        }

    def run(self):
        if not self.exists:
            self.fetch_images()


if __name__ == '__main__':
    t = DAFavs()
    t.run()
