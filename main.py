import os
import sys
import argparse
import typing as tp
from getpass import getpass

import pandas as pd
from tqdm import tqdm
from yandex_music.client import Client, Playlist, Track

from VKMP import main as vkmp_main


def usage():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', '-f', help='csv dump file to import')
    parser.add_argument('--user', '-u', help='yandex login')
    parser.add_argument('--like', help='like tracks', action='store_true')
    parser.add_argument('--playlist', help='playlist name to create', default='VK2YA')
    parser.add_argument('--prompt', help='manual select tracks for multiple choices', action='store_true')
    return parser.parse_args()


def load_dump_tracks(path):
    print(f'Load dump: {path}')
    vk = pd.read_csv(path, usecols=[0, 1])
    vk.columns = ['artist', 'title']
    return vk


def search_track(client: Client, artist: str, title: str, prompt=False) -> tp.Union[None, Track]:

    def _search(text, results):
        search = client.search(text)
        if search.best and search.best.type == 'track':
            result = search.best.result
            if result.title.lower() == title.lower() and any(artist.lower() == a.name.lower() for a in result.artists):
                return result
            results.append(result)
        if search.tracks:
            for i, result in enumerate(search.tracks.results):
                if result.title.lower() == title.lower() and any(artist.lower() == a.name.lower() for a in result.artists):
                    return result
                results.append(result)
                if i == 4:
                    break
        return None

    results = []
    r = _search(title, results)
    if r is None:
        r = _search(f'{artist} {title}', results)
    if r is None and prompt:
        for i, r in enumerate(results):
            print(f"{i}. {', '.join(a.name for a in r.artists) - {r.title}}")
        a = input("{} - {} [1/n] ".format(artist, title))
        if not a:
            return results[0]
        if not a.isdigit():
            return None
        a = int(a)
        return results[a] if a < len(results) else None
    return r


def get_yandex_liked_tracks(client):
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


def get_tracks_from_playlist(client, playlist_name='VK2YA'):
    ya_tracks = []
    for short_track in create_playlist(client, playlist_name).tracks:
        track = short_track.track
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
        return client.users_playlists(playlists[name].kind)[0]
    print(f'Creating playlist: {name}')
    return client.users_playlists_create(name)


def get_ya_music_client(user=None) -> Client:
    login = user or input('Yandex login: ')
    password = getpass('Password / One time password (from Yandex.Key): ')
    return Client.from_credentials(login, password)


def add_tracks(client: Client, tracks: tp.List[Track], playlist_name=None, like=False):
    print(f"Adding tracks to playlist: {playlist_name} {'and like' if like else ''}")
    kind = create_playlist(client, name=playlist_name).kind
    error_tracks = set()
    for track in tracks:
        print(f'Insert track: {track.artist} - {track.title} to {playlist_name}', end=' ')
        p = client.users_playlists_insert_track(kind, track.id, track.albums[0].id if track.albums else 0)
        if p is None:
            print('NOT OK')
            error_tracks.add(track)
        else:
            print('OK')
        if like:
            print(f'Like: {track.artist} - {track.title}', end=' ')
            if not client.users_likes_tracks_add(track.id):
                print('NOT OK')
                error_tracks.add(track)
            else:
                print('OK')
    print('Complete')
    return error_tracks


def main():

    args = usage()

    # Load tracks from file or from VKMP
    if args.file and not os.path.exists(args.file):
        print(f"File {args.file} doesn't exists")
        sys.exit(1)
    elif not args.file:
        vk_args = vkmp_main.usage()
        vk_args.csv = True
        print('VKMP Export')
        vkmp_main.main(vk_args)

    file = args.file or vkmp_main.DUMP_FILE
    if not os.path.exists(file):
        print(f"File {file} doesn't exists")
        sys.exit(1)

    vk = load_dump_tracks(file)

    # Get Yandex.Music client
    client = get_ya_music_client(args.user)
    # Get already imported tracks
    ya = get_tracks_from_playlist(client, playlist_name=args.playlist)


    # Get difference between dump tracks and playlist
    new_tracks = vk[~(vk.title.str.lower().isin(ya.title.str.lower()) & vk.artist.str.lower().isin(ya.artist.str.lower()))]

    print(f'Dump tracks: {len(vk)}')
    print(f'Tracks in playlist {args.playlist}: {len(ya)}')
    print(f'New tracks to import: {len(new_tracks)}')

    # Search tracks at Yandex.Music
    not_found = []
    tracks_to_add = []
    for _,t in tqdm(new_tracks.iterrows(), desc='Searching Yandex.Music'):
        track = search_track(client, t.artist, t.title, prompt=args.prompt)
        if track is None:
            not_found.append(t)
            continue
        tracks_to_add.append(track)

    # Add tracks to Yandex.Music playlist
    error_tracks = add_tracks(client, tracks_to_add, playlist_name=args.playlist, like=args.like)
    print('-'*20)
    print(f'Imported tracks: {len(tracks_to_add) - len(error_tracks)}')
    print(f'Not imported tracks: {len(error_tracks)}')



if __name__ == '__main__':
    main()
