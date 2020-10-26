import os
import logging
import yamlsettings

from services.PixelsService import PixelsService
from services.YouTubeService import YouTubeService


config = yamlsettings.load('config/config.yaml')
logger = logging.getLogger()

# fstrings can use any placeholder from the video object
# ref: https://www.pexels.com/api/documentation/#videos-overview
title_fstring = 'RID TEST - {id}'
description_fstring = """
This video is sourced from https://www.pexels.com/
Original uploader: {user[name]} - {user[url]}

This video is uploaded to be used as a software test.
"""


def main():
    # Get video from Pixels
    pixels = PixelsService(config)
    vid_obj = pixels.get_random_video()
    file_id = pixels.get_lowest_res_id(vid_obj)
    local_file_path = pixels.download_video(vid_obj, file_id)

    # Upload that video to YT
    yt = YouTubeService(config)
    yt.initialize_upload(
        vid_path=local_file_path,
        title=title_fstring.format(**vid_obj),
        description=description_fstring.format(**vid_obj),
        tags=[],
        category_id=22,
        privacy_status='unlisted'
    )

    # Cleanup local files
    os.remove(local_file_path)


if __name__ == "__main__":
    main()
