import requests
import random
import math
import os


class PixelsService():
    def __init__(self, config):
        self.config = config
        self.url = self.config.get('PIXELS_URL')
        self.s = requests.Session()
        self.s.headers.update({"Authorization": self.config.get('PIXELS_KEY')})

    def get_videos(self, page=1):
        params = {
            "max_duration": self.config.get('PIXELS_MAX_DURATION', 60),
            "page": page
        }
        resp = self.s.get(
            f'{self.url}/videos/popular',
            params=params,
        )
        resp.raise_for_status()
        vids = resp.json()
        return vids

    def get_random_video(self):
        all_vids = self.get_videos()
        total_vids = all_vids.get('total_results')
        per_page = all_vids.get('per_page')
        random_page = math.floor(random.random() * (total_vids / per_page))
        random_vid_index = math.floor(random.random() * per_page)
        r_page = self.get_videos(page=random_page)
        random_vid = r_page.get('videos')[random_vid_index]
        return random_vid

    def get_lowest_res_id(self, video_obj):
        files = video_obj.get('video_files')
        min_res_width = 999999999
        min_res_id = None
        for f in files:
            w = f.get('width')
            if w is not None and w < min_res_width:
                min_res_width = w
                min_res_id = f.get('id')
        return min_res_id

    def download_video(self, vid_obj, file_id):
        download_url = ""
        for v in vid_obj.get('video_files'):
            if v.get('id') == file_id:
                download_url = v.get('link')
                break

        filename = download_url.split('?')[0].split('/')[-1]
        local_file_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                self.config.get(
                    'LOCAL_VID_FOLDER',
                    '../videos'
                ),
                filename
            )
        )
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(local_file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return local_file_path
