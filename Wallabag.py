import os
import glob
import json
import re
import logging
import requests
import settings
import keys
from shutil import copyfileobj
from common import cached_property
from common import url2slug
from pprint import pprint

RE_FNAME = re.compile(r"(?P<id>[0-9]+)_(?P<slug>.*).epub")


class Wallabag(object):
    def __init__(self):
        self.access_token = ""
        self.auth = {}

    @property
    def tdir(self):
        return settings.paths.bookmarks

    @cached_property
    def existing(self):
        return [
            os.path.basename(fpath)
            for fpath in glob.glob(os.path.join(self.tdir, "*"))
        ]

    def archive_batch(self, entries):
        for entry in entries["_embedded"]["items"]:
            ename = url2slug(entry["url"])
            eid = entry["id"]
            fname = f"{ename}.epub"
            target = os.path.join(self.tdir, fname)

            if fname in self.existing:
                logging.debug("skipping existing entry %s", entry["id"])
            else:
                with requests.get(
                    f"{keys.wallabag.url}/api/entries/{eid}/export.epub",
                    stream=True,
                    headers=self.auth,
                ) as r:
                    logging.info("saving %s to %s", eid, target)
                    with open(target, "wb") as f:
                        copyfileobj(r.raw, f)

    def run(self):
        tparams = {
            "grant_type": "password",
            "client_id": keys.wallabag.client_id,
            "client_secret": keys.wallabag.client_secret,
            "username": keys.wallabag.username,
            "password": keys.wallabag.password,
        }
        token = requests.post(
            f"{keys.wallabag.url}/oauth/v2/token", data=tparams
        )
        try:
            tdata = token.json()
            if "access_token" not in tdata:
                logging.error(
                    "missing access token from wallabag response"
                )
                return
        except Exception as e:
            logging.error("failed to get token from wallabag: %s", e)
            return

        self.access_token = tdata["access_token"]
        self.auth = {"Authorization": f"Bearer {self.access_token}"}

        r = requests.get(
            f"{keys.wallabag.url}/api/entries", headers=self.auth
        )
        try:
            entries = r.json()
        except Exception as e:
            logging.error(
                "failed to get first page from wallabag: %s", e
            )
            return

        batch = entries["limit"]
        pages = entries["pages"]
        page = entries["page"]
        self.archive_batch(entries)
        while page < pages:
            page = page + 1
            paged = {"perPage": batch, "page": page}
            r = requests.get(
                f"{keys.wallabag.url}/api/entries",
                params=paged,
                headers=self.auth,
            )
            entries = r.json()
            self.archive_batch(entries)


if __name__ == "__main__":
    wbag = Wallabag()
    wbag.run()
