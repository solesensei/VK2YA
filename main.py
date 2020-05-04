import os
import sys
import argparse
import typing as tp
from getpass import getpass

import pandas as pd

from tqdm import tqdm
from yandex_music.client import Client, Playlist, Track

from VKMP import main as vkmp_main

from utils import echo, color


def usage():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', '-f', help='csv dump file to import')
    parser.add_argument('--user', '-u', help='yandex login')
    parser.add_argument('--like', help='like tracks', action='store_true')
    parser.add_argument('--playlist', help='playlist name to create', default='VK2YA')
    parser.add_argument('--clear', help='clear playlist before import', action='store_true')
    parser.add_argument('--reverse', help='insert tracks in reversed order', action='store_true')
    parser.add_argument('--no-clear-duplicates', help='do not remove duplicates tracks from playlist', action='store_true')
    parser.add_argument('--prompt', help='manual select multiple choices tracks', action='store_true')
    return parser.parse_args()


def load_dump_tracks(path):
    echo.c(f'Load dump: ./{path}')
    vk = pd.read_csv(path, usecols=[0, 1])
    vk.columns = ['artist', 'title']
    return vk.drop_duplicates()


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
            echo(f"{i}. {', '.join(a.name for a in r.artists)} - {r.title}")
        a = input(color.y("{} - {} [1/n] defaul: n ".format(artist, title)))
        if not a or not a.isdigit():
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
    ya = pd.DataFrame(ya_tracks).drop_duplicates()
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
    ya = pd.DataFrame(ya_tracks, columns=['title', 'artist', 'album', 'year', 'genre']).drop_duplicates()
    ya.album.fillna('', inplace=True)
    ya.genre.fillna('', inplace=True)
    ya.year.fillna(0, inplace=True)
    ya.year = ya.year.astype(int)
    return ya


def remove_playlist_duplicates(client: Client, playlist_name='VK2YA') -> Playlist:
    echo.c(f'Removing duplicates from playlist: {playlist_name}')
    p = create_playlist(client, playlist_name)
    unique_tracks = set()
    while len(p.tracks) != len(unique_tracks):
        was_len = len(p.tracks)
        unique_tracks = set()
        for i, t in enumerate(p.tracks):
            if t.id in unique_tracks:
                echo.y(f'Duplicate found: {t.track.artists[0].name} - {t.track.title}, removing')
                client.users_playlists_delete_track(p.kind, i, i+1, revision=p.revision)
                p = create_playlist(client, playlist_name)
                break
            unique_tracks.add(t.id)
        if was_len == len(p.tracks):
            break  # recurse


def clear_playlist(client: Client, name='VK2YA'):
    echo.y(f'Clearing playlist: {name}')
    p = create_playlist(client, name)
    client.users_playlists_delete_track(p.kind, 0, p.track_count, revision=p.revision)


def create_playlist(client: Client, name='VK2YA') -> Playlist:
    playlists = {p.title: p for p in client.users_playlists_list()}
    if name in playlists:
        return client.users_playlists(playlists[name].kind)[0]
    echo.g(f'Creating playlist: {name}')
    return client.users_playlists_create(name)


def get_ya_music_client(user=None) -> Client:
    login = user or input(color.y('Yandex login: '))
    password = getpass(color.y('Password / One time password (from Yandex.Key): '))
    return Client.from_credentials(login, password)


def add_tracks(client: Client, tracks: tp.List[Track], playlist_name=None, like=False, reversed_order=False):
    if not tracks:
        echo.y('No tracks to add')
        return set()

    echo.g(f"Adding tracks to playlist: {playlist_name} {'and like' if like else ''} {len(tracks)}")

    p = create_playlist(client, name=playlist_name)
    error_tracks = set()
    for track in tracks if reversed_order else reversed(tracks):
        echo.c(f"Insert track: {', '.join(a.name for a in track.artists)} - {track.title} to {playlist_name}", end=' ')
        p = client.users_playlists_insert_track(p.kind, track.id, track.albums[0].id if track.albums else 0, revision=p.revision)
        if p is None:
            echo.r('NOT OK')
            error_tracks.add(track)
        else:
            echo.g('OK')
        if like:
            echo.c(f"Like: {', '.join(a.name for a in track.artists)} - {track.title}", end=' ')
            if not client.users_likes_tracks_add(track.id):
                echo.r('NOT OK')
                error_tracks.add(track)
            else:
                echo.g('OK')
    echo.g('Complete!')
    return error_tracks


def dump_error_tracks(tracks: tp.List[Track], file='errors.csv'):
    with open(file, 'w') as f:
        f.write('artist,title\n')
        for t in tracks:
            artists = ', '.join(a.name for a in t.artists)
            f.write(f'"{artists}","{t.title}"\n')


def dump_not_found_tracks(tracks: tp.List[pd.DataFrame], file='not_found.csv'):
    with open(file, 'w') as f:
        f.write('artist,title\n')
        for t in tracks:
            f.write(f'"{t.artist}","{t.title}"\n')


def main():

    args = usage()

    # Load tracks from file or from VKMP
    if args.file and not os.path.exists(args.file):
        echo.r(f"File {args.file} doesn't exists")
        sys.exit(1)
    elif not args.file:
        vk_args = vkmp_main.usage()
        vk_args.csv = True
        echo.y('VKMP Export')
        vkmp_main.main(vk_args)

    file = args.file or vkmp_main.DUMP_FILE
    if not os.path.exists(file):
        echo.r(f"File {file} doesn't exists")
        sys.exit(1)

    vk = load_dump_tracks(file)

    # Get Yandex.Music client
    client = get_ya_music_client(args.user)
    # Clear playlist
    if args.clear:
        clear_playlist(client, name=args.playlist)
    # Get already imported tracks
    ya = get_tracks_from_playlist(client, playlist_name=args.playlist)

    # Get difference between dump tracks and playlist
    new_tracks = vk[~(vk.title.str.lower().isin(ya.title.str.lower()) & vk.artist.str.lower().isin(ya.artist.str.lower()))]

    echo(f"{color.c('Dump tracks:')} {len(vk)}")
    echo(f"{color.c('Tracks in playlist ' + args.playlist)}: {len(ya)}")
    echo(f"{color.c('Tracks to import:')} {len(new_tracks)}")

    # Search tracks at Yandex.Music
    not_found = []
    tracks_to_add = []
    for _, t in tqdm(new_tracks.iterrows(), desc=color.y('Searching Yandex.Music'), total=len(new_tracks)):
        track = search_track(client, t.artist, t.title, prompt=args.prompt)
        if track is None:
            not_found.append(t)
            continue
        tracks_to_add.append(track)

    # Add tracks to Yandex.Music playlist
    error_tracks = add_tracks(client, tracks_to_add, playlist_name=args.playlist, like=args.like, reversed_order=args.reverse)

    # Clear duplicates
    if not args.no_clear_duplicates:
        remove_playlist_duplicates(client, playlist_name=args.playlist)

    dump_not_found_tracks(not_found)
    dump_error_tracks(error_tracks)

    echo.c('-'*20)
    echo(f"{color.c('Imported tracks:')} {len(tracks_to_add) - len(error_tracks)}")
    echo(f"{color.c('Not found tracks:')} {len(not_found)}")
    echo(f"{color.c('Not imported tracks:')} {len(error_tracks)}")


if __name__ == '__main__':
    main()
