# PyLabRobot Resource Locator Program (PLR-RLP)

PyLabRobot Resource Locator Program (PLR-RLP) is a utility program to help you calibrate iSWAP movements on Hamilton STAR (and other robots in the future). It is designed to be used with [PyLabRobot](https://github.com/pylabrobot/pylabrobot).

## Installation

1. Clone PyLabRobot:

```sh
git clone https://github.com/PyLabRobot/pylabrobot
```

2. Install PyLabRobot Resource Locator Program with cloned PyLabRobot:

```sh
git clone https://github.com/PyLabRobot/resource-locator-program
cd resource-locator-program
virtualenv env
source env/bin/activate
pip install -e '/path/to/pylabrobot[dev]'
pip install -e .
```

## Usage

```sh
python iswap.py
```

