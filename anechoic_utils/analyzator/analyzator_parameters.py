from enum import Enum, unique
from itertools import product
from typing import List
from dataclasses import dataclass


@unique
class FrequencyTypes(Enum):
    HZ = "HZ"
    MHZ = "MHZ"
    GHZ = "GHZ"


@dataclass
class FrequencyParameters:
    start: float = None
    stop: float = None
    frequency_type: FrequencyTypes = None
    num_points: int = None


@unique
class AnalyzatorType(Enum):
    ROHDE_SCHWARZ = 'ROHDE_SCHWARZ'
    CEYEAR = 'CEYEAR'
    PLANAR = 'PLANAR'


@unique
class ResultsFormatType(Enum):
    DB = "DB"
    LIN = "LIN"
    PHASE = "PHASE"
    SMITH = "SMITH"
    POLAR = "POLAR"
    REAL = "REAL"
    IMAG = "IMAG"

    def __str__(self) -> str:
        return self.value.lower()


class SParameters:
    def __init__(self, ports: List = [1, 2]):
        self.ports = ports
        self.repeat, self.prefix = 2, 'S'
        self.parameters = [f'{self.prefix}{p1}{p2}' for (p1, p2)
                           in product(ports, repeat=self.repeat)]

    @property
    def enum(self):
        return Enum('SParameters', {p: p for p in self.parameters})

    @property
    def type(self):
        return type(self.enum)


if __name__ == "__main__":
    params = SParameters().enum
    print(params.S11._value)
