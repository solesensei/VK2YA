# VK2YA

Simple script to transfer VK Music to Yandex.Music.

It works with [VKMP](https://github.com/solesensei/VKMP) music collector, written by [@BpArCuCTeMbI](https://github.com/BpArCuCTeMbI/VKMP).

You can also use any **CSV dump** as input in the following format: `artist,title`. 
## Requirements

- Python 3.7

## Setup

```bash
pip install -r requirements.txt

# for VKMP
pip install -r VKMP/requirements.txt
```

## Usage

```bash
# show help message
python main.py -h

# fetch tracks with VKMP and import to Yandex.Music playlist name VK2YA
python main.py --playlist VK2YA

# load tracks from dump.csv (no VKMP) and import to Yandex.Music playlist VK2YA
python main.py --file dump.csv --playlist VK2YA

# import tracks from dump.csv to playlist VK2YA and like them
python main.py --file dump.csv -u <yandex-login> --like

# resume importing, skip not found tracks and already imported tracks
python main.py --file dump.csv -u <yandex-login> --resume
```
