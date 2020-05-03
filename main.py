import os
import argparse
from getpass import getpass

import pandas as pd
from yandex_music.client import Client, Playlist, Track

from VKMP import main as vkmp_main


def usage():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='VKMP')
    subparsers.add_parser("vkmp", parents=[vkmp_main.usage()], add_help=False)
    parser.add_argument('--file', '-f', help='csv dump file to import')
    parser.add_argument('--user', '-u', help='yandex login')
    return parser.parse_args()


def load_dump_tracks(path):
    vk = pd.read_csv(path)
    vk.columns = ['title', 'artist', 'time']
    return vk


def load_yandex_liked_tracks(client):
    ya_tracks = []
    for liked_track in client.users_likes_tracks().tracks:
        track_id = liked_track.track_id
        track = client.tracks(track_id)[0]
        ya_tracks.append(
            {
                'title': track.title,
                'artist': ",".join(artist.name for artist in track.artists),
                'album': track.albums[0].title if track.albums else None,
                'year': track.albums[0].year if track.albums else None,
                'genre': track.albums[0].genre if track.albums else None
            }
        )
    ya = pd.DataFrame(ya_tracks)
    ya.album.fillna('', inplace=True)
    ya.genre.fillna('', inplace=True)
    ya.year.fillna(0, inplace=True)
    ya.year = ya.year.astype(int)
    return ya


def create_playlist(client: Client, name='VK2YA') -> Playlist:
    playlists = {p.title: p for p in client.users_playlists_list()}
    if name in playlists:
        return client.users_playlists(playlists[name].kind)
    return client.users_playlists_create(name)


def get_ya_music_client(user=None) -> Client:
    login = user or input('Yandex login: ')
    password = getpass('Password / One time password (from Yandex.Key): ')
    return Client.from_credentials(login, password)


def main():

    args = usage()

    # Load tracks from file or from VKMP
    if args.file and not os.path.exists(args.file):
        print(f"File {args.file} doesn't exists")
        exit(1)
    elif not args.file:
        args.csv = True
        vkmp_main.main(args)

    file = args.file or vkmp_main.DUMP_FILE
    if not os.path.exists(file):
        print(f"File {file} doesn't exists")
        exit(1)

    vk = load_dump_tracks(file)

    # Get Yandex.Music client
    client = get_ya_music_client(args.user)
    playlist = create_playlist(client)


if __name__ == '__main__':
    main()
