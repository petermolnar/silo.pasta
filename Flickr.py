import os
import glob
import flickr_api
from bleach import clean
import arrow
import keys
import common
import settings
from pprint import pprint
import logging

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

    def run(self):
        pages = 1
        page = 1
        while page <= pages:
            #try:
            fetched = self.user.getFavorites(
                user_id=self.user.id,
                #extras=','.join([
                    #'description',
                    #'geo',
                    #'tags',
                    #'owner_name',
                    #'date_upload',
                    #'url_o',
                    #'url_k',
                    #'url_h',
                    #'url_b',
                    #'url_c',
                    #'url_z',
                #]),
                #'min_fave_date': self.lastpulled
                page=page
            )
            for p in fetched:
                photo = FlickrFav(p)
                photo.run()
            pages = fetched.info.pages
            page = page + 1


class FlickrFav(common.ImgFav):
    def __init__(self, flickrphoto):
        self.flickrphoto = flickrphoto
        self.info = flickrphoto.getInfo()
        self.owner = self.info.get('owner')

    def __str__(self):
        return "fav-of %s" % (self.url)

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
        for maybe in ['Original', 'Large 2048', 'Large 1600', 'Large']:
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

#https://api.flickr.com/services/rest/?method=flickr.favorites.getPublicList&api_key=80a5c2e7fdad3ed1304298850caab99d&user_id=36003160%40N08&per_page=500&format=json&nojsoncallback=1


#class FlickrFavs(Favs):
    #url = 'https://api.flickr.com/services/rest/'

    #def __init__(self):
        #super().__init__('flickr')
        #self.get_uid()
        #self.params = {
            #'method': 'flickr.favorites.getList',
            #'api_key': shared.config.get('api_flickr', 'api_key'),
            #'user_id': self.uid,
            #'extras': ','.join([
                #'description',
                #'geo',
                #'tags',
                #'owner_name',
                #'date_upload',
                #'url_o',
                #'url_k',
                #'url_h',
                #'url_b',
                #'url_c',
                #'url_z',
            #]),
            #'per_page': 500,  # maximim
            #'format': 'json',
            #'nojsoncallback': '1',
            #'min_fave_date': self.lastpulled
        #}

    #def get_uid(self):
        #params = {
            #'method': 'flickr.people.findByUsername',
            #'api_key': shared.config.get('api_flickr', 'api_key'),
            #'format': 'json',
            #'nojsoncallback': '1',
            #'username': shared.config.get('api_flickr', 'username'),
        #}
        #r = requests.get(
            #self.url,
            #params=params
        #)
        #parsed = json.loads(r.text)
        #self.uid = parsed.get('user', {}).get('id')

    #def getpaged(self, offset):
        #logging.info('requesting page #%d of paginated results', offset)
        #self.params.update({
            #'page': offset
        #})
        #r = requests.get(
            #self.url,
            #params=self.params
        #)
        #parsed = json.loads(r.text)
        #return parsed.get('photos', {}).get('photo', [])

    #def run(self):
        #r = requests.get(self.url, params=self.params)
        #js = json.loads(r.text)
        #js = js.get('photos', {})

        #photos = js.get('photo', [])

        #total = int(js.get('pages', 1))
        #current = int(js.get('page', 1))
        #cntr = total - current

        #while cntr > 0:
            #current = current + 1
            #paged = self.getpaged(current)
            #photos = photos + paged
            #cntr = total - current

        #for photo in photos:
            #fav = FlickrFav(photo)
            #if not fav.exists:
                #fav.run()
            ## fav.fix_extension()
