#!/usr/bin/env python3
import configparser
import datetime
import json
import logging
import os
import sys
import tarfile
from dataclasses import dataclass
from socket import gaierror

import requests
from paramiko import SSHClient
from scp import SCPClient
from urllib3.exceptions import InsecureRequestWarning

from collectorless_client import b64_pwd
from collectorless_client.plugin.plugin_executor import execute_plugin

LOGGER: logging.Logger = logging.getLogger("collectorless")


@dataclass
class CCOCredentials:
    """Struct containing the user's CCO credentials.

    :param cco_id: cisco.com id
    :type cco_id: str
    :param cco_password: cisco.com password
    :type cco_password: str
    """

    cco_id: str
    cco_password_base64: str

    @property
    def cco_password(self):
        if b64_pwd.is_b64_encoded(self.cco_password_base64):
            return b64_pwd.decode(self.cco_password_base64)
        return self.cco_password_base64


@dataclass
class ApiMConfig:
    """Struct encoding the APIx portion of the [cisco_transfer] section of the Collectorless configuration
    file (settings.conf).
    The factory classmethod, load() should be used in favor of manual instantiation.

    :param client_id: client id from apiconsole.cisco.com
    :type client_id: str
    :param client_secret: client secret from apiconsole.cisco.com
    :type client_secret: str
    """

    client_id: str
    client_secret_base64: str

    @classmethod
    def load(cls, config_filepath: str) -> "ApiMConfig":
        """Factory method for this struct. Given a config file, uses configparser to load attributes.

        :param config_filepath: absolute path of the Collectorless configuration file
        :type config_filepath: str
        :return: ApiXConfig instance
        """
        cparser = configparser.ConfigParser(
            allow_no_value=True, inline_comment_prefixes="#"
        )
        cparser.read(config_filepath)
        return ApiMConfig(
            client_id=cparser.get("cisco_transfer", "client_id"),
            client_secret_base64=cparser.get("cisco_transfer", "client_secret"),
        )

    @classmethod
    def load_env(cls) -> "ApiMConfig":
        """Factory method for this struct. Uses environment variables to load attributes.

        :return: ApiXConfig instance
        """
        return ApiMConfig(
            client_id=os.environ["COL_TRANSFER_CLIENT_ID"],
            client_secret_base64=os.environ["COL_TRANSFER_CLIENT_SECRET"]
        )

    @property
    def client_secret(self):
        if b64_pwd.is_b64_encoded(self.client_secret_base64):
            return b64_pwd.decode(self.client_secret_base64)
        return self.client_secret_base64


@dataclass
class CxDriveConfig:
    """Struct encoding the cxDrive portion of the [cisco_transfer] section of the Collectorless configuration
    file (settings.conf).
    The factory classmethod, load() should be used in favor of manual instantiation.

    :param collector_id: NP collector ID
    :type collector_id: str
    :param transport: method of transport (https or scp)
    :type transport: str
    """

    collector_id: str
    transport: str
    host_key_file: str

    @classmethod
    def load(cls, config_filepath: str) -> "CxDriveConfig":
        """Factory method for this struct. Given a config file, uses configparser to load attributes.

        :param config_filepath: absolute path of the Collectorless configuration file
        :type config_filepath: str
        :return: CxDriveConfig instance
        """
        cparser = configparser.ConfigParser(
            allow_no_value=True, inline_comment_prefixes="#"
        )
        cparser.read(config_filepath)
        return CxDriveConfig(
            collector_id=cparser.get("cisco_transfer", "collector_id"),
            transport=cparser.get("cisco_transfer", "transport"),
            host_key_file=cparser.get("cisco_transfer", "host_key_file"),
        )

    @classmethod
    def load_env(cls, collector_id_var_name: str) -> "CxDriveConfig":
        """Factory method for this struct. Uses environment variables to load attributes.

        :param collector_id_var_name: name of the environment variable used to store the collector_id. It is a parameter
                                      to allow for one customer to have multiple collectors running with different ids
        :type collector_id_var_name: str
        :return: CxDriveConfig instance
        """
        return CxDriveConfig(collector_id=os.environ[collector_id_var_name],
                             transport=os.environ["COL_TRANSFER_TRANSPORT"],
                             host_key_file=os.environ["COL_TRANSFER_HOST_KEY_FILE"])


class Uploader:
    """Uploader object, contains all logic required to upload an archive file to CX Drive.

    :param cx_drive: Cx drive configuration object
    :type cx_drive: CxDriveConfig

    :param apim: Api configuration object
    :type apim: ApiMConfig

    :param archive_path: Path where to save encoded transport file
    :type archive_path: str6
    """

    def __init__(self, cco_credentials: CCOCredentials,
                 cx_drive: CxDriveConfig,
                 apim: ApiMConfig,
                 archive_path: str) -> None:
        requests.packages.urllib3.disable_warnings(
            category=InsecureRequestWarning
        )  # pylint: disable=no-member
        self._cco_credentials = cco_credentials
        self._cx_drive = cx_drive
        self._apim = apim
        self._archive_path = archive_path

    def _get_cxd_access_token(self) -> str:
        """Retrieves CXD Access Token from APIM.

        :param cco_credentials: user's CCO credentials
        :type cco_credentials: CCOCredentials
        :return: CXD access token
        """
        LOGGER.info("Attempting authentication with cloudsso.cisco.com")
        url = "https://cloudsso.cisco.com/as/token.oauth2"
        params = {
            "grant_type": "password",
            "client_id": self._apim.client_id,
            "client_secret": self._apim.client_secret,
            "username": self._cco_credentials.cco_id,
            "password": self._cco_credentials.cco_password,
        }
        try:
            response = requests.post(url, params=params, verify=True)
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.ConnectionError as err:
            LOGGER.error(
                f"Connection Error with cloudsso.cisco.com while getting access token.\n{err}"
            )
            raise
        except json.JSONDecodeError:
            LOGGER.error(
                f"Unexpected response from cloudsso.cisco.com while getting access token.\nResponse:\n{response.text}"
            )
            raise
        try:
            access_token = result["access_token"]
            LOGGER.info("Authentication success.")
        except KeyError:
            if "error" in result:
                LOGGER.error(
                    f"Error encountered while requesting access token:\nError: {result['error']}\n"
                    f"Description: {result['error_description']}"
                )
            else:
                LOGGER.error(
                    f"Unexpected response from cloudsso.cisco.com: {json.dumps(result)}"
                )
            LOGGER.info("Authentication failed.")
        return access_token

    def _get_cxd_upload_token(self, access_token: str) -> str:
        """Retreives CXD upload token from api.cisco.com.

        :param access_token: CXD access token
        :type access_token: str
        :return: CXD upload token
        """
        url = f"https://api.cisco.com/api/collectorless/v1/token/{self._cx_drive.collector_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        try:
            response = requests.post(url, headers=headers, verify=True)
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.ConnectionError as err:
            LOGGER.error(
                f"Connection Error with api.cisco.com while getting upload token.\n{err}"
            )
            raise
        except json.JSONDecodeError:
            LOGGER.error(
                f"Unexpected response from api.cisco.com while getting upload token.\nResponse:\n{response.text}"
            )
            raise
        try:
            upload_token = result["token"]
        except KeyError:
            LOGGER.error(
                f"Unexpected response from api.cisco.com while getting upload token.\nResponse:\n{result}"
            )
            raise
        return upload_token

    @staticmethod
    def progress(filename, size, sent):
        sys.stdout.write(
            "%s's progress: %.2f%%   \r" % (filename, float(sent) / float(size) * 100)
        )

    def _transfer_scp(self, upload_file: str, upload_token: str) -> None:
        """Transfers the archive file via SCP.

        :param upload_file: full path of archive to upload to CX Drive
        :type upload_file: str
        :param upload_token: CXD upload token
        :type upload_token: str
        """
        try:
            ssh = SSHClient()
            ssh.load_system_host_keys()
            ssh.load_host_keys(self._cx_drive.host_key_file)
            ssh.connect(
                "cxd.cisco.com",
                username=self._cx_drive.collector_id,
                password=upload_token,
            )
            with SCPClient(ssh.get_transport(), progress=self.progress) as scp:
                scp.put(upload_file)
        except gaierror as err:
            LOGGER.error(f"Error establishing connection. \n{err}")
            raise
        except FileNotFoundError as err:
            LOGGER.error(f"File does not exist! \n{err}")
            raise
        except Exception as err:
            LOGGER.error(f"Unexpected exception while trying to scp file. \n{err}")
            raise

    def _transfer_https(self, upload_file: str, upload_token) -> None:
        """Transfers the archive file via HTTPS.

        :param upload_file: full path of archive to upload to CX Drive
        :type upload_file: str
        :param upload_token: CXD upload token
        :type upload_token: str
        """
        session = requests.Session()
        session.auth = (self._cx_drive.collector_id, upload_token)
        try:
            file_name = os.path.basename(upload_file)
            response = session.put(
                f"https://cxd.cisco.com/home/{file_name}",
                data=open(upload_file, "rb"),
                verify=True,
                headers={"Expect": "100-continue"}
                )
        except requests.exceptions.ConnectionError as err:
            LOGGER.error(f"Connection Error with cxd.cisco.com\n{err}")
            raise
        except FileNotFoundError as err:
            LOGGER.error(f"File does not exist! \n{err}")
            raise
        try:
            assert (
                    response.status_code == requests.codes.created
            )  # pylint: disable=no-member
        except AssertionError:
            LOGGER.error(f"Status code is {response.status_code}, not 201!")
            raise

    def _compress(self, upload_dir):
        """Create a tar.gz archive of the results folder.

        :return: output file path
        """
        if not os.path.isdir(upload_dir):
            LOGGER.error(f"Directory {upload_dir} does not exist!")
            raise FileNotFoundError(f"Directory {upload_dir} does not exist!")
        LOGGER.info(f"Creating dir {self._archive_path} if it does not exist.")
        os.makedirs(self._archive_path, exist_ok=True)
        output_filename = os.path.join(
            self._archive_path,
            "{}.tar.gz".format(str(datetime.datetime.now().strftime("%Y%m%d%H%M%S"))),
        )
        LOGGER.info(
            f"Creating archive {output_filename} from directory {upload_dir}."
        )
        try:
            with tarfile.open(output_filename, "w:gz") as tar:
                for f_name in os.listdir(upload_dir):
                    dir_to_tar = os.path.join(upload_dir, f_name)
                    tar.add(dir_to_tar, arcname=os.path.basename(f_name))
        except FileExistsError:
            LOGGER.error(f"Archive file {output_filename} already exists!")
            raise
        return output_filename

    def _execute_pre_upload_plugin(self, upload_dir: str, collector_name: str):
        execute_plugin(collector_name, upload_dir)

    def upload(self, upload_dir: str, collector_name: str) -> None:
        """Main method of the Uploader class. Calls required private methods based on configuration.

        :param upload_dir: full path to collected data
        :type upload_dir: str
        :param collector_name: Name of running collector
        :type collector_name: str
        """
        if self._cx_drive.transport not in ("scp", "https"):
            raise AttributeError(
                f"Invalid transport method configured: {self._cx_drive.transport}. Please use 'https' or 'scp'."
            )

        self._execute_pre_upload_plugin(upload_dir, collector_name)

        upload_transport = self._compress(upload_dir)
        LOGGER.info(f"Uploading archive file at {upload_transport}.")
        access_token = self._get_cxd_access_token()
        upload_token = self._get_cxd_upload_token(access_token)
        LOGGER.debug(upload_token)
        LOGGER.info(f"Attempting upload via {self._cx_drive.transport}.")
        if self._cx_drive.transport == "scp":
            self._transfer_scp(upload_transport, upload_token)
        elif self._cx_drive.transport == "https":
            self._transfer_https(upload_transport, upload_token)
        LOGGER.info("Upload success!")
