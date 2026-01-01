import json
import logging
import os
import tempfile
from collections.abc import Generator
from threading import Event
from typing import Any, Literal

from pydantic import BaseModel

import youtube

ChannelUploadFilter = Literal["all_videos", "full_videos_only", "livestreams_only", "shorts_only"]
PlaylistEntryFilter = Literal["all_videos", "new_entries_from_the_top"]


class ThreadStoppedError(Exception):
    pass


class SettingsGlobal(BaseModel):
    name: str
    target_playlist_id: str
    selector: ChannelUploadFilter


class PerChannelSettings(BaseModel):
    selector: ChannelUploadFilter


class PerPlaylistSettings(BaseModel):
    selector: PlaylistEntryFilter


class SettingsChannels(BaseModel):
    channel_name: str
    seen_video_ids: list[str]
    settings: PerChannelSettings | None = None


class SettingsPlaylists(BaseModel):
    playlist_name: str
    seen_video_ids: list[str]
    settings: PerPlaylistSettings


class Settings(BaseModel):
    global_settings: SettingsGlobal
    channels: dict[str, SettingsChannels]
    playlists: dict[str, SettingsPlaylists]


def grab_specific_setting(global_settings: SettingsGlobal, local_settings: PerChannelSettings | PerPlaylistSettings | None, what_to_grab: str) -> Any:
    try:
        return getattr(local_settings, what_to_grab, getattr(global_settings, what_to_grab))
    except AttributeError as error:
        raise AttributeError(f"Requested field {what_to_grab} present in neither global nor local settings.") from error


def read_settings(file: str) -> Settings:
    with open(file, encoding="utf-8") as f:
        raw = json.load(f)
        return Settings(**raw)


def write_settings(file: str, settings: Settings) -> None:
    # Serialize settings to JSON
    json_str = settings.model_dump_json(indent=4)

    dir_name = os.path.dirname(os.path.abspath(file))
    # Create a temporary file in the same directory
    with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tmp_file:
        tmp_file.write(json_str)
        temp_name = tmp_file.name

    try:
        os.replace(temp_name, file)  # Atomically replace the original file with the temp file
    except Exception as e:
        if os.path.exists(temp_name):  # Clean up temp file if something goes wrong
            os.remove(temp_name)
        raise e


def process_old(file: str, stop_event: Event) -> Generator[tuple[str, int, int]]:
    data = read_settings(file)
    global_settings = data.global_settings
    process_name = global_settings.name
    target_playlist = youtube.Playlist(global_settings.target_playlist_id)

    yield f"Initializing {process_name}", 0, len(data.channels)

    for i, (channel_id, channel_elem) in enumerate(data.channels.items()):
        if stop_event.is_set():
            raise ThreadStoppedError
        channel_name = channel_elem.channel_name
        yield f"{process_name} \n {channel_name}", i, len(data.channels)
        channel_seen_list = channel_elem.seen_video_ids
        logging.debug("Channel seen list: %s", channel_seen_list)
        channel_selector = grab_specific_setting(global_settings, channel_elem.settings, "selector")

        try:
            c = youtube.Channel(channel_id)
            videos_to_add: list[str] = []
            for video_id in c.list_uploads(
                full_videos_only=channel_selector == "full_videos_only",
                livestreams_only=channel_selector == "livestreams_only",
                shorts_only=channel_selector == "shorts_only",
            ):
                logging.info("Video ID: %s - %s", video_id, type(video_id))
                if stop_event.is_set():
                    raise ThreadStoppedError
                if video_id in channel_seen_list:
                    break
                videos_to_add.append(video_id)
            success = True
            for i, video_id in enumerate(reversed(videos_to_add)):
                if stop_event.is_set():
                    raise ThreadStoppedError
                success = bool(success * target_playlist.add_video(video_id))
                if success:
                    channel_seen_list.insert(0, video_id)
                    channel_seen_list = channel_seen_list[0 : int(os.getenv("keep_video_ids", "50"))]
                    if i > 15 and i % 10 == 0:
                        data.channels[channel_id].seen_video_ids = channel_seen_list
                        write_settings(file, data)
            if success:
                data.channels[channel_id].seen_video_ids = channel_seen_list
                write_settings(file, data)
        except youtube.SkippableError as error:
            logging.error("Skippable exception caught - will be skipped over. Channel: %s - Msg: %s", channel_name, str(error))


def process(file: str, stop_event: Event) -> Generator[tuple[str, int, int]]:
    data = read_settings(file)
    global_settings = data.global_settings
    process_name = global_settings.name
    target_playlist = youtube.Playlist(global_settings.target_playlist_id)

    yield f"Initializing {process_name}", 0, len(data.channels)

    for i, (channel_id, channel_elem) in enumerate(data.channels.items()):
        if stop_event.is_set():
            raise ThreadStoppedError
        channel_name = channel_elem.channel_name
        yield f"{process_name} \n {channel_name}", i, len(data.channels)
        channel_seen_list = channel_elem.seen_video_ids
        logging.debug("Channel seen list: %s", channel_seen_list)
        channel_selector = grab_specific_setting(global_settings, channel_elem.settings, "selector")

        try:
            c = youtube.Channel(channel_id)
            videos_to_add: list[str] = []
            for video_id in c.list_uploads(
                full_videos_only=channel_selector == "full_videos_only",
                livestreams_only=channel_selector == "livestreams_only",
                shorts_only=channel_selector == "shorts_only",
            ):
                logging.info("Video ID: %s - %s", video_id, type(video_id))
                if stop_event.is_set():
                    raise ThreadStoppedError
                if video_id in channel_seen_list:
                    break
                videos_to_add.append(video_id)
            full_success = True
            for i, video_id in enumerate(reversed(videos_to_add)):
                if stop_event.is_set():
                    raise ThreadStoppedError
                this_success = target_playlist.add_video(video_id)
                full_success = bool(full_success * this_success)
                if this_success:
                    channel_seen_list.insert(0, video_id)
                    channel_seen_list = channel_seen_list[0 : int(os.getenv("keep_video_ids", "50"))]
                    if i > 15 and i % 10 == 0:
                        data.channels[channel_id].seen_video_ids = channel_seen_list
                        write_settings(file, data)
            if full_success:
                data.channels[channel_id].seen_video_ids = channel_seen_list
                write_settings(file, data)
        except youtube.SkippableError as error:
            logging.error("Skippable exception caught - will be skipped over. Channel: %s - Msg: %s", channel_name, str(error))

    for i, (playlist_id, playlist_elem) in enumerate(data.playlists.items()):
        if stop_event.is_set():
            raise ThreadStoppedError
        playlist_name = playlist_elem.playlist_name
        yield f"{process_name} \n {playlist_name}", i, len(data.playlists)
        playlist_seen_list = playlist_elem.seen_video_ids
        logging.debug("Playlist seen list: %s", playlist_seen_list)
        playlist_selector: PlaylistEntryFilter = grab_specific_setting(global_settings, playlist_elem.settings, "selector")

        try:
            p = youtube.Playlist(playlist_id)
            videos_to_add = []
            for video_elem in p.yield_elements(["contentDetails"]):
                video_id = video_elem["contentDetails"]["videoId"]
                logging.info("Video ID: %s - %s", video_id, type(video_id))
                if stop_event.is_set():
                    raise ThreadStoppedError
                if playlist_selector == "new_entries_from_the_top" and video_id in playlist_seen_list:
                    break

                if video_id not in playlist_seen_list:
                    videos_to_add.append(video_id)
            full_success = True
            for i, video_id in enumerate(reversed(videos_to_add)):
                if stop_event.is_set():
                    raise ThreadStoppedError
                this_success = target_playlist.add_video(video_id)
                full_success = bool(full_success * this_success)
                if this_success:
                    playlist_seen_list.insert(0, video_id)
                    if i > 15 and i % 10 == 0:
                        data.playlists[playlist_id].seen_video_ids = playlist_seen_list
                        write_settings(file, data)
            data.playlists[playlist_id].seen_video_ids = playlist_seen_list
            write_settings(file, data)
        except youtube.SkippableError as error:
            logging.error(
                "Skippable exception caught - will be skipped over. Playlist: %s - Playlist ID: %s - Msg: %s", playlist_name, playlist_id, str(error)
            )


def create(filename: str, name: str, target_playlist_id: str, selector: ChannelUploadFilter) -> None:
    if os.path.isfile(f"auto_adder_config/{filename}"):
        raise youtube.SkippableError("Auto adder can't be created, the file already exists.")
    data = read_settings("auto_adder_config/template.json")
    data.global_settings.name = name
    data.global_settings.target_playlist_id = target_playlist_id
    data.global_settings.selector = selector
    write_settings(f"auto_adder_config/{filename}", data)
