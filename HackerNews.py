import os
import glob
import logging
import json
import requests
from common import cached_property
import settings
import keys

class HackerNews(object):
    url = "https://hacker-news.firebaseio.com/v0/"

    @property
    def tdir(self):
        return os.path.join(settings.paths.get("archive"), "hn")

    @cached_property
    def existing(self):
        return [os.path.basename(fpath).replace(".json", "") for fpath in glob.glob(os.path.join(self.tdir, "*.json"))]

    def run(self):
        user = keys.hackernews.get("username")
        content = requests.get(f"{self.url}/user/{user}.json")
        data = content.json()
        if "submitted" not in data:
            return
        for entry in data["submitted"]:
            if entry in self.existing:
                logging.debug("skipping HackerNews entry %s", entry)
                continue
            entry_data = requests.get(f"{self.url}/item/{entry}.json")
            target = os.path.join(self.tdir, f"{entry}.json")
            with open(target, "wt") as f:
                logging.info("saving HackerNews entry %s", entry)
                f.write(json.dumps(entry_data.json(), indent=4, ensure_ascii=False))


if __name__ == "__main__":
    hn = HackerNews()
    hn.run()
