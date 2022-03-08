import os
import uuid

from collections import defaultdict
from tarfile import TarFile
from typing import DefaultDict
from unittest.mock import MagicMock
from urllib.parse import urlparse

import requests
from requests.auth import HTTPBasicAuth


class UploadedFileMock:
    def __init__(self, uploaded_file_buffer):
        self._tar_file = TarFile.open(fileobj=uploaded_file_buffer, mode="r:gz")

    def get_file_from_uploaded_transport(self, file_name, first_level_random=True):
        full_path = file_name
        if first_level_random:
            top_level_random_dir = self.filelist[0]
            full_path = os.path.join(top_level_random_dir, file_name)

        self._tar_file.extract(full_path, path="/tmp")
        full_path_extracted = os.path.join("/tmp", full_path)
        data = open(full_path_extracted, "rb").read().decode()
        os.remove(full_path_extracted)
        return data

    @property
    def filelist(self):
        return self._tar_file.getnames()


class CXDriveMock:
    _credentials: dict = {}
    _auth_tokens: DefaultDict[str, list] = defaultdict(list)
    _upload_tokens: DefaultDict[str, list] = defaultdict(list)
    files_uploaded: list = []

    def __init__(self, http):
        self._http = http
        self._query = {}
        self.query_missing = {}
        self.auth_register = MagicMock()

    def start(self):
        self._http.add_call(
            "POST",
            "https://cloudsso.cisco.com/as/token.oauth2",
            params="*",
            side_effect=self._auth,
        )

        self._http.add_call(
            "POST",
            "https://api.cisco.com/api/collectorless/v1/token/collector_id_123",
            side_effect=self._verify_token,
        )
        self._http.add_call(
            # Should be https://cxd.cisco.com/home/* but we don't support regexp - cannot give a filename at this stage
            "PUT", "*", side_effect=self._upload, code=201, data="*"
        )

    def _upload(self, *_, **kwargs):
        uploaded_file = kwargs["data"]
        collector_id, upload_token = self._http.session_mock.auth
        if (
            upload_token in self._upload_tokens[collector_id] and kwargs["headers"]["Expect"] == "100-continue"
        ):
            self.file_uploaded = UploadedFileMock(uploaded_file)
            return {
                "return_value": "file uploaded",
                "code": 201,
            }

        else:
            return {
                "return_value": "Invalid auth token",
                "code": 401,
            }

    def _verify_token(self, _, url, **kwargs):
        collector_id = urlparse(url).path.split("/")[-1]
        token = kwargs["headers"]["Authorization"].split(" ")[1]
        if token in self._auth_tokens[collector_id]:
            upload_token = str(uuid.uuid4())
            self._upload_tokens[collector_id].append(upload_token)
            return {
                "return_value": {"token": upload_token},
                "code": 200,
            }
        else:
            return {
                "return_value": "Invalid auth token",
                "code": 401,
            }

    def _auth(self, *args, **kwargs):
        credentials = kwargs["params"]
        credentials_index = self._credentials_index(**credentials)
        self.auth_register(**credentials)
        if credentials_index in self._credentials:
            return {
                "return_value": {
                    "access_token": self._generate_access_token(
                        self._credentials[credentials_index]
                    )
                },
                "code": 200,
            }
        else:
            return {
                "return_value": "Not authorized",
                "code": 401,
            }

    def _generate_access_token(self, collector_id):
        access_token = str(uuid.uuid4())
        self._auth_tokens[collector_id].append(access_token)
        return access_token

    def stop(self):
        self._credentials = {}
        self._auth_tokens = defaultdict(list)
        self.files_uploaded = []
        self.auth_register.reset_mock()

    def add_user(
        self, client_id, client_secret, username, grant_type, password, collector_id
    ):
        credentials_index = self._credentials_index(
            client_id, client_secret, username, grant_type, password
        )

        self._credentials[credentials_index] = collector_id

    def _credentials_index(
        self, client_id, client_secret, username, grant_type, password
    ):

        return "{client_id}-{client_secret}{username}-{grant_type}-{password}".format(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            grant_type=grant_type,
            password=password,
        )

    def query(self, method, url, call):
        query = call["json"]["query"]
        call.pop("verify_ssl")
        call["auth"] = HTTPBasicAuth(call["auth"].login, call["auth"].password)
        try:
            return {"return_value": {"results": self._query[query]}, "code": 200}
        except KeyError:

            if self.TRACK_MISSING_QUERIES:
                res = requests.request(method, url, verify=False, **call)
                res.raise_for_status()
                print("self.add_query('''%s''', %s)" % (query, res.json()["results"]))
                raise
            return {
                "return_value": "NOT FOUND query not registered: {}",
                "code": 404,
            }
