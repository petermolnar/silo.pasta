import common
import settings
import Tumblr
import LastFM
import DeviantArt
import Flickr
import Artstation
from pprint import pprint

lfm = LastFM.LastFM()
lfm.run()

opml = common.Follows()

silos = [
    DeviantArt.DAFavs(),
    Flickr.FlickrFavs(),
    Tumblr.TumblrFavs(),
    Artstation.ASFavs(),
]

for silo in silos:
    silo.run()
    opml.update({silo.silo: silo.feeds})

opml.sync()
opml.export()
