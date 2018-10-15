import common
import settings
import Tumblr
import LastFM
import DeviantArt
import Flickr
from pprint import pprint

lfm = LastFM.LastFM()
lfm.run()

opml = common.Follows()

silos = [
    DeviantArt.DAFavs(),
    Flickr.FlickrFavs(),
    Tumblr.TumblrFavs()
]

for silo in silos:
    silo.run()
    opml.append(silo.silo, silo.feeds)

opml.export()
