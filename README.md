# VK2YA

Simple script to transfer VK Music to Yandex.Music.

## Setup

```bash
pip install -r requirements.txt && pip install -r VKMP/requirements.txt
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

```
