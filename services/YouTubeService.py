#!/usr/bin/python

import http.client
import httplib2
import os
import random
import sys
import time
import yamlsettings
import logging

from googleapiclient import channel
from googleapiclient import mimeparse
from googleapiclient import model

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow


logger = logging.getLogger()

# Explicitly tell the underlying HTTP transport library not to retry, since
# we are handling retry logic ourselves.
httplib2.RETRIES = 1

# Maximum number of times to retry before giving up.
MAX_RETRIES = 10

# Always retry when these exceptions are raised.
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError, http.client.NotConnected,
                        http.client.IncompleteRead, http.client.ImproperConnectionState,
                        http.client.CannotSendRequest, http.client.CannotSendHeader,
                        http.client.ResponseNotReady, http.client.BadStatusLine)

# Always retry when an apiclient.errors.HttpError with one of these status
# codes is raised.
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

# This OAuth 2.0 access scope allows an application to upload files to the
# authenticated user's YouTube channel, but doesn't allow other types of access.
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# This variable defines a message to display if the CLIENT_SECRETS_FILE is
# missing.
MISSING_CLIENT_SECRETS_MESSAGE = """
WARNING: Please configure OAuth 2.0

To make this sample run you will need to populate the client_secrets.json file
found at:

     {path}

with information from the API Console
https://console.developers.google.com/

For more information about the client_secrets.json file format, please visit:
https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
"""

VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")


class YouTubeService():
    def __init__(self, config: dict):
        self.config = config
        self.yt = self._get_authenticated_service()

    def _get_authenticated_service(self):
        client_secrets_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                self.config.get(
                    'YT_CLIENT_SECRETS_FILE_PATH',
                    '../config/client_secrets.json'
                )
            )
        )
        flow = flow_from_clientsecrets(
            client_secrets_path,
            scope=YOUTUBE_UPLOAD_SCOPE,
            message=MISSING_CLIENT_SECRETS_MESSAGE.format(
                path=client_secrets_path
            )
        )

        cred_storage_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                self.config.get(
                    'YT_CLIENT_CRED_STORAGE_PATH',
                    '../config/yt-oauth2.json'
                )
            )
        )
        storage = Storage(cred_storage_path)
        credentials = storage.get()

        if credentials is None or credentials.invalid:
            credentials = run_flow(flow, storage)

        return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
                     http=credentials.authorize(httplib2.Http()))

    # This method implements an exponential backoff strategy to resume a
    # failed upload.
    def _resumable_upload(self, insert_request):
        response = None
        error = None
        retry = 0
        while response is None:
            try:
                logger.info("Uploading file...")
                _, response = insert_request.next_chunk()
                if response is not None:
                    if 'id' in response:
                        return response.get('id')
                    else:
                        logger.critical(
                            f"The upload failed with an unexpected response: {response}"
                        )
                        return None
            except HttpError as e:
                if e.resp.status in RETRIABLE_STATUS_CODES:
                    error = f"A retriable HTTP error {e.resp.status} occurred:\n{e.content}"
                else:
                    raise
            except RETRIABLE_EXCEPTIONS as e:
                error = f"A retriable error occurred:\n{e}"

            if error is not None:
                logger.error(error)
                retry += 1
                if retry > MAX_RETRIES:
                    logger.critical("No longer attempting to retry.")
                    return

                max_sleep = 2 ** retry
                sleep_seconds = random.random() * max_sleep
                logger.info(
                    f"Sleeping {sleep_seconds:.1f} seconds and then retrying..."
                )
                time.sleep(sleep_seconds)

    def initialize_upload(self, vid_path: str, title: str, description: str, tags: [str],
                          category_id: int, privacy_status: str):
        body = dict(
            snippet=dict(
                title=title,
                description=description,
                tags=tags,
                categoryId=category_id
            ),
            status=dict(
                privacyStatus=privacy_status
            )
        )

        # Call the API's videos.insert method to create and upload the video.
        # pylint: disable=no-member
        insert_request = self.yt.videos().insert(
            part=",".join(body.keys()),
            body=body,
            # The chunksize parameter specifies the size of each chunk of data, in
            # bytes, that will be uploaded at a time. Set a higher value for
            # reliable connections as fewer chunks lead to faster uploads. Set a lower
            # value for better recovery on less reliable connections.
            #
            # Setting "chunksize" equal to -1 in the code below means that the entire
            # file will be uploaded in a single HTTP request. (If the upload fails,
            # it will still be retried where it left off.) This is usually a best
            # practice, but if you're using Python older than 2.6 or if you're
            # running on App Engine, you should set the chunksize to something like
            # 1024 * 1024 (1 megabyte).
            media_body=MediaFileUpload(
                vid_path, chunksize=-1, resumable=True)
        )

        return self._resumable_upload(insert_request)
