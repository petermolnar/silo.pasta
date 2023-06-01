import common
import settings
import Tumblr
import LastFM
import DeviantArt
import Flickr
#import Artstation
import HackerNews
from pprint import pprint

silos = [
    Flickr.FlickrFavs(),
    Tumblr.TumblrFavs(),
    DeviantArt.DAFavs(),
#    Artstation.ASFavs(),
#    LastFM.LastFM(),
    HackerNews.HackerNews()
]

for silo in silos:
    silo.run()
