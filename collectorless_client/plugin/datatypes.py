from dataclasses import dataclass, field
from typing import List


@dataclass
class Snmp:
    snmp_type: str
    oid: str
    value: str


@dataclass
class Cli:
    command: str
    output: str


@dataclass()
class Config:
    config_type: str
    config: str


@dataclass
class Device:
    snmp: List[Snmp]
    cli: List[Cli]
    syslog: str
    device_id: str
    config: List[Config] = field(default_factory=list)
