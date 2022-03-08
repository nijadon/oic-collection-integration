import contextlib
import datetime
import json
import logging
import os
import shutil
import tarfile


logger = logging.getLogger(__name__)


@contextlib.contextmanager
def clean_up(base_path: str):
    yield
    _clean_transport_paths(base_path)


def _clean_transport_paths(base_path):
    try:
        shutil.rmtree(os.path.join(base_path, "transport"))
    except FileNotFoundError:
        pass

    try:
        for subdir in os.listdir(base_path):
            os.remove(os.path.join(base_path, subdir))
    except FileNotFoundError:
        pass


def write_metadata(base_path: str, metadata: dict):
    """

    :param base_path: path to the collector directory output (e.g usually .../ACI_collector_data
    :param metadata: dictionary with the metadata information
    """
    transport_path = os.path.join(base_path, "transport")
    metadata_file_path = os.path.join(transport_path, "metadata.json")
    with open(metadata_file_path, "w") as fd:
        json.dump(metadata, fd)


def compress(source_base_path: str, destination_dir_path: str = "") -> str:
    """
    Used to create the .tar.gz from a "transport" directory on customer device.

    :param source_base_path: Root directory path, where a "transport" directory can be found.
    :param destination_dir_path: Destination where the .tar.gz file should be saved.
    :return: path to the resulting .tar.gz file
    """
    if not destination_dir_path:
        destination_dir_path = source_base_path

    input_transport_path = os.path.join(source_base_path, "transport")
    transport_file_name = "{}.tar.gz".format(
        str(datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    )
    transport_file_path = os.path.join(destination_dir_path, transport_file_name)

    try:
        with tarfile.open(transport_file_path, "w:gz") as tar:
            tar.add(
                input_transport_path,
                arcname=os.path.basename(input_transport_path)
            )
    except FileExistsError:
        logger.error(f"Archive file {transport_file_path} already exists!")
        raise
    return transport_file_path
