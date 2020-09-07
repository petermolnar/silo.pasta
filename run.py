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
    DeviantArt.DAFavs(),
    Flickr.FlickrFavs(),
    Tumblr.TumblrFavs(),
#    Artstation.ASFavs(),
    LastFM.LastFM(),
    HackerNews.HackerNews()
]

for silo in silos:
    silo.run()
