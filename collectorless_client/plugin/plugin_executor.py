import importlib
import json
import logging
import os
from typing import List

import dataclasses

from collectorless_client.plugin.datatypes import Device

logger = logging.getLogger(__name__)


def _discovery_plugin(pkg: str):
    plugins = "{}.plugin".format(pkg)
    try:
        plugin_module = importlib.import_module(plugins)
    except ModuleNotFoundError:
        logger.info("No plugin found for {pkg}".format(pkg=pkg))
        return
    return getattr(plugin_module, "add_custom", None)


def _save_device_data(device, data_name, device_path):
    data_path = os.path.join(device_path, "{}.json".format(data_name))
    with open(data_path, "w") as fd:
        json.dump([dataclasses.asdict(data) for data in getattr(device, data_name)], fd)


def _save_data(custom_data: List[Device], data_path: str):
    custom_data_path = os.path.join(data_path, "CUSTOM")
    os.makedirs(custom_data_path, exist_ok=True)
    for device in custom_data or []:
        device_path = os.path.join(custom_data_path, device.device_id)
        os.makedirs(device_path)
        _save_device_data(device, "snmp", device_path)
        _save_device_data(device, "config", device_path)
        _save_device_data(device, "cli", device_path)


def execute_plugin(pkg: str, data_path: str):
    plugin_fn = _discovery_plugin(pkg)
    if not plugin_fn:
        return
    custom_data = plugin_fn()

    _save_data(custom_data, data_path)
