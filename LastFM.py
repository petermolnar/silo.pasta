import os
import csv
import json
import logging
from operator import attrgetter
from collections import namedtuple
import requests
import arrow
from datetime import datetime
import settings
import keys
from pprint import pprint
from math import floor
from common import cached_property
import sys

Track = namedtuple(
    "Track", ["timestamp", "artist", "album", "title", "artistid", "albumid", "img"]
)

class LastFM(object):
    url = "http://ws.audioscrobbler.com/2.0/"

    def __init__(self):
        self.params = {
            "method": "user.getrecenttracks",
            "user": keys.lastfm.get("username"),
            "api_key": keys.lastfm.get("key"),
            "format": "json",
            "limit": "200",
        }
        # if os.path.isfile(self.target):
            # mtime = os.path.getmtime(self.target)
            # self.params.update({"from": mtime})

    @property
    def target(self):
        return os.path.join(settings.paths.get("archive"), "lastfm.csv")

    @cached_property
    def existing(self):
        timestamps = []
        if os.path.isfile(self.target):
            with open(self.target, "r") as f:
                r = csv.reader(f)
                for row in r:
                    try:

                        timestamps.append(int(datetime.fromisoformat(row[0]).timestamp()))
                    except Exception as e:
                        logging.error("arrow failed on row %s as: %s", row[0], e)
                        continue
        return timestamps

    @property
    def exists(self):
        return os.path.isfile(self.target)

    def extracttracks(self, data):
        tracks = []
        if not data:
            return tracks
        for track in data.get("track", []):
            if "date" not in track:
                continue
            ts = arrow.get(int(track.get("date").get("uts")))
            if ts.timestamp in self.existing:
                continue
            entry = Track(
                ts.format("YYYY-MM-DDTHH:mm:ssZZ"),
                track.get("artist").get("#text", ""),
                track.get("album").get("#text", ""),
                track.get("name", ""),
                track.get("artist").get("mbid", ""),
                track.get("album").get("mbid", ""),
                track.get("image", [])[-1].get("#text", ""),
            )
            tracks.append(entry)
        return tracks

    def fetch(self):
        r = requests.get(self.url, params=self.params)
        return json.loads(r.text).get("recenttracks")

    def run(self):
        if len(self.existing):
            self.params.update({"from": sorted(self.existing)[-1]})
        #startpage = max(1, floor(len(self.existing) / int(self.params.get("limit"))))
        #startpage = 1
        self.params.update({"page": 1})
        try:
            data = self.fetch()
            tracks = self.extracttracks(data)
            total = int(data.get("@attr").get("totalPages"))
            current = int(data.get("@attr").get("page"))
            cntr = total - current
        except Exception as e:
            logging.error("Something went wrong: %s", e)
            return

        if not len(tracks):
            return

        while cntr > 0:
            current = current + 1
            cntr = total - current
            logging.info("requesting page #%d of paginated results", current)
            self.params.update({"page": current})
            data = self.fetch()
            tracks = tracks + self.extracttracks(data)

        if not self.exists:
            with open(self.target, "w") as f:
                writer = csv.DictWriter(f, fieldnames=Track._fields)
                writer.writeheader()

        if len(tracks):
            with open(self.target, "a") as f:
                writer = csv.writer(f, quoting=csv.QUOTE_NONNUMERIC)
                writer.writerows(sorted(tracks, key=attrgetter("timestamp")))


if __name__ == "__main__":
    lfm = LastFM()
    lfm.run()
