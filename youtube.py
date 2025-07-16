import os
import logging
from typing import Generator, Literal, Optional, Any
import json
import re
from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow #type:ignore
from googleapiclient.discovery import build #type:ignore
from googleapiclient.errors import HttpError #type:ignore

class UnskippableException(Exception):
    pass
class SkippableException(Exception):
    pass
class ResourceNotFoundException(SkippableException):
    pass
class InvalidValueException(SkippableException):
    pass

def wrap_execute(request:Any) -> Any:
    original_execute = request.execute
    def wrapped_execute(*args:Any, **kwargs:Any) -> Any:
        try:
            return original_execute(*args, **kwargs)
        except HttpError as e:
            status = e.resp.status
            reason = e.error_details[0] if hasattr(e, "error_details") else str(e)
            logging.error("[YouTube API Error] Status %s: %s", status, reason)
            # if status == 403:
            #     print("Quota or permissions issue.")
            if status == 404 and "The playlist identified with the request's <code>playlistId</code> parameter cannot be found." in str(reason):
                logging.warning("Resource not found.")
                raise ResourceNotFoundException from e
            elif status == 400 and "Invalid Value" in str(reason):
                logging.warning("Invalid Value.")
                raise ResourceNotFoundException from e
            # elif status == 400:
            #     print("Bad request.")
            raise
    request.execute = wrapped_execute
    return request

class ServiceWrapper:
    def __init__(self, service: Any) -> None:
        self._service = service

    def __getattr__(self, name:str) -> Any:
        attr = getattr(self._service, name)
        if callable(attr):
            def method_wrapper(*args: Any, **kwargs: Any) -> Any:
                sub_resource = attr(*args, **kwargs)
                return _wrap_request_methods(sub_resource)
            return method_wrapper
        return attr

class RequestWrapper:
    def __init__(self, resource: Any) -> None:
        self._resource = resource
    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._resource, name)
        if callable(attr):
            def request_creator(*args: Any, **kwargs: Any) -> Any:
                request = attr(*args, **kwargs)
                return wrap_execute(request)
            return request_creator
        return attr
def _wrap_request_methods(resource: Any) -> RequestWrapper:
    return RequestWrapper(resource)

def build_with_wrapped_execute(*args: Any, **kwargs: Any) -> ServiceWrapper:
    return ServiceWrapper(build(*args, **kwargs))

class Youtube:
    def __init__(self) -> None:
        load_dotenv()
        self.scope = ['https://www.googleapis.com/auth/youtube.force-ssl']
        self.creds = self._authorize(self.scope)
        self.build = build_with_wrapped_execute("youtube", "v3", credentials= self.creds)
    def _authorize(self, scopes:list[str]) -> Credentials:
        def get_new_creds() -> Credentials:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_path, scopes
            )
            creds = flow.run_local_server(
                port= 8080,
                access_type= 'offline',
                prompt='consent',
                timeout_seconds= 120
            )
            return creds
        def read_creds() -> Credentials:
            creds = Credentials.from_authorized_user_file( #type:ignore
                client_token_path,
                scopes
            )
            return creds
        creds = None
        client_secret_path = os.getenv('GOOGLE_CLIENT_SECRET', 'credentials.json')
        assert client_secret_path
        client_token_path = os.getenv('GOOGLE_CLIENT_TOKEN', 'token.json')
        assert client_token_path

        if os.path.exists(client_token_path):
            creds = read_creds()

        if not creds or not creds.valid:
            if creds and creds.expired:
                if creds.refresh_token:
                    creds.refresh(Request()) #type:ignore
                else:
                    creds = get_new_creds()
            else:
                creds = get_new_creds()

            with open(client_token_path, "w", encoding= 'utf-8') as token:
                token.write(creds.to_json()) #type:ignore

        return creds

class Video(Youtube):
    VIDEO_PATTERN = r'(?:https?://(?:www\.)?(?:(?:youtube\.com/(?:watch\?v=|shorts/)|youtu.be/)))?([\w\-]{11})'
    def __init__(self, video_id:str):
        super().__init__()
        self.id = self._get_id(video_id)
    def _get_id(self, string:str) -> str:
        matched = re.match(self.VIDEO_PATTERN, string)
        if matched:
            return matched.group(1)

        return string
    def get_data(
            self,
            part:list[
                Literal[
                    "contentDetails",
                    "fileDetails",
                    "id",
                    "liveStreamingDetails",
                    "localizations",
                    "paidProductPlacementDetails",
                    "player",
                    "processingDetails",
                    "recordingDetails",
                    "snippet",
                    "statistics",
                    "status",
                    "suggestions",
                    "topicDetails",
                ]
            ],
            fields: Optional[str] = None
        ) -> Optional[dict]:
        #doc: https://developers.google.com/youtube/v3/docs/videos/list
        request = self.build.videos().list( #pylint:disable=no-member
            part=','.join(part),
            fields= fields,
            id=self.id,
            maxResults=1
        )
        response = request.execute()
        return response["items"][0]
    def verify(self) -> bool:
        try:
            result = self.get_data(['id'])
            assert result
            return 'id' in result and result['id'] == self.id
        except IndexError:
            return False

class Playlist(Youtube):
    PLAYLIST_PATTERN = r'https?://(?:www\.)?youtube\.com/playlist\?list=([\w\-]+)'
    def __init__(self, playlist_id:str):
        super().__init__()
        self.id = self._get_id(playlist_id)
    def _get_id(self, string:str) -> str:
        matched = re.match(self.PLAYLIST_PATTERN, string)
        if matched:
            return matched.group(1)

        return string
    def yield_elements(
            self,
            part:list[
                Literal[
                    'contentDetails',
                    'snippet',
                    'id',
                    'status'
                ]
            ],
            fields: Optional[str] = None
        ) -> Generator[dict, None, None]:
        #docs: https://developers.google.com/youtube/v3/docs/playlistItems/list
        next_page_token = None
        while True:
            request = self.build.playlistItems().list( #pylint:disable=no-member
                part=','.join(part),
                fields= fields,
                playlistId=self.id,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()
            yield from response['items']

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                return
    def add_video(self, video_id:str) -> bool:
        try:
            request = self.build.playlistItems().insert( #pylint:disable=no-member
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": self.id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id
                        }
                    }
                }
            )
            response = request.execute()
            logging.info(json.dumps(response, indent= 4))
            logging.info(response)
            return "id" in response
        except HttpError as error:
            logging.error('An error occurred while adding video %s to playlist %s: %s', video_id, self.id, error)
            return False
    def get_video_playlist_id(self, video_id:str) -> str | Literal[False]:
        for video_element in self.yield_elements(['id', 'snippet']):
            logging.info(json.dumps(video_element, indent= 4))
            if video_element['snippet']['resourceId']['videoId'] == video_id:
                return video_element["id"]
        return False
    def remove_video(
            self,
            video_id: Optional[str] = None,
            video_playlist_id:Optional[str] = None
        ) -> bool:

        assert video_id or video_playlist_id, 'Either argument video_id or video_playlist_id must be provided.'
        try:
            if video_playlist_id is None:
                assert video_id
                tmp_results = self.get_video_playlist_id(video_id)
                assert tmp_results
                video_playlist_id = tmp_results

            del_request = self.build.playlistItems().delete( #pylint:disable=no-member
                id= video_playlist_id
            )
            del_request.execute()
            return True
        except AssertionError:
            logging.warning('Video %s not found in playlist %s, there could not be removed.', video_id, self.id)
        except HttpError as error:
            logging.error('An error occurred while removing video %s from playlist %s: %s', video_id, self.id, error)
        return False

    def verify(self) -> bool:
        try:
            request = self.build.playlistItems().list( #pylint:disable=no-member
                part='id',
                playlistId=self.id,
                maxResults=1,
            )
            request.execute()
            return True
        except (ResourceNotFoundException, InvalidValueException):
            return False

class Channel(Youtube):
    CHANNEL_ID_PATTERN = r'https?://(?:www\.)?youtube\.com/channel/(UC[\w\-]{22})$'
    CHANNEL_HANDLE_PATTERN = r'https?://(?:www\.)?youtube\.com/(@[\w\-]+)$'
    def __init__(self, channel_id:str):
        super().__init__()
        self.id = self._get_id(channel_id)
        self.playlist_upload_id:Optional[str] = None
    def _get_id(self, string:str) -> str:
        matched = re.match(self.CHANNEL_ID_PATTERN, string)
        if matched:
            return matched.group(1)

        matched = re.match(self.CHANNEL_HANDLE_PATTERN, string)
        if matched:
            return self._convert_handle_to_id(matched.group(1))

        if string.startswith('@'):
            return self._convert_handle_to_id(string)

        return string
    def _convert_handle_to_id(self, handle:str) -> str:
        request = self.build.channels().list( #pylint:disable=no-member
            part='id',
            forHandle = handle,
        )
        response = request.execute()
        if response and 'items' in response and 'id' in response['items'][0]:
            return response['items'][0]['id']
        raise UnskippableException(f'Some unknown BS happened while turning a Channel handle into a Channel ID. Response: {response}')

    def get_data(
            self,
            part: list[
                Literal[
                    "auditDetails",
                    "brandingSettings",
                    "contentDetails",
                    "contentOwnerDetails",
                    "id",
                    "localizations",
                    "snippet",
                    "statistics",
                    "status",
                    "topicDetails",
                ]
            ],
            fields: Optional[str] = None) -> dict:
        request = self.build.channels().list( #pylint:disable=no-member
            part=','.join(part),
            fields= fields,
            id=self.id,
        )
        response = request.execute()
        logging.info(json.dumps(response, indent= 4))
        return response
    def get_upload_playlist(self, full_videos_only:bool = False, livestreams_only:bool = False, shorts_only:bool = False) -> Playlist:
        if not self.playlist_upload_id:
            data = self.get_data(
                ['contentDetails'],
                'items/contentDetails/relatedPlaylists/uploads'
            )
            if not data:
                raise ResourceNotFoundException(
                    f'Upload playlist of {self.id} could not be found due to an empty data response. '
                    'Channel deleted? Potential workaround: set channel settings to "all_videos".'
                )
            self.playlist_upload_id = data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        assert self.playlist_upload_id

        if full_videos_only:
            return Playlist(
                self.playlist_upload_id.replace('UU', 'UULF', 1)
            )
        if livestreams_only:
            return Playlist(
                self.playlist_upload_id.replace('UU', 'UULV', 1)
            )
        if shorts_only:
            return Playlist(
                self.playlist_upload_id.replace('UU', 'UUSH', 1)
            )
        return Playlist(self.playlist_upload_id)

    def get_profile_image(self, specific_size:int|bool = False) -> str:
        thumbnails:dict = self.get_data(
            part=['snippet'],
            fields= 'items/snippet/thumbnails'
        )['items'][0]['snippet']['thumbnails']

        max_height = -1
        max_url = ''
        for thumbnail in thumbnails.values():
            if specific_size and max_height >= specific_size:
                return max_url
            if thumbnail['height'] > max_height:
                max_url = thumbnail['url']
                max_height = thumbnail['height']

        if specific_size:
            return max_url.replace(f's{max_height}', f's{specific_size}')
        return max_url

    def list_uploads(
            self,
            size:Optional[int] = None,
            full_videos_only:bool = False,
            livestreams_only:bool = False,
            shorts_only:bool = False
        ) -> list[str]:
        '''Returns video ID list of uploads, NEWEST FIRST.'''
        result:list[str] = []
        p = self.get_upload_playlist(full_videos_only=full_videos_only, livestreams_only=livestreams_only, shorts_only=shorts_only)
        for video_element in p.yield_elements(part=['snippet'], fields='items/snippet/resourceId/videoId'):
            video_id = video_element['snippet']['resourceId']['videoId']
            result.append(video_id)
            if size and len(result) >= size:
                break
        return result

    def verify(self) -> bool:
        result = self.get_data(['id'])
        return 'items' in result and 'id' in result['items'][0] and result['items'][0]['id'] == self.id

def add_video_to_playlist(src_video_id:str, target_playlist_id:Optional[str] = None, target_playlist:Optional[Playlist] = None) -> bool:
    assert target_playlist_id or target_playlist, 'Neither target playlist ID nor playlist object given, one is required.'
    if target_playlist is None:
        assert target_playlist_id
        target_playlist = Playlist(target_playlist_id)
    return target_playlist.add_video(src_video_id)
def add_playlist_to_playlist(
        src_playlist_id:Optional[str] = None,
        src_playlist:Optional[Playlist] = None,
        target_playlist_id:Optional[str] = None,
        target_playlist:Optional[Playlist] = None
    ) -> bool:
    assert src_playlist_id or src_playlist, 'Neither source playlist ID nor playlist object given, one is required.'
    if src_playlist is None:
        assert src_playlist_id
        src_playlist = Playlist(src_playlist_id)
    assert target_playlist_id or target_playlist, 'Neither target playlist ID nor playlist object given, one is required.'
    if target_playlist is None:
        assert target_playlist_id
        target_playlist = Playlist(target_playlist_id)

    success = True
    for video_element in src_playlist.yield_elements(part=['snippet'], fields='items/snippet/resourceId/videoId'):
        video_id = video_element['snippet']['resourceId']['videoId']
        success = bool(success * target_playlist.add_video(video_id))
    return success
def add_channeluploads_to_playlist(
        src_channel_id:Optional[str] = None,
        src_channel:Optional[Channel] = None,
        target_playlist_id:Optional[str] = None,
        target_playlist:Optional[Playlist] = None,
        full_videos_only:bool = False,
        livestreams_only:bool = False,
        shorts_only:bool = False
    ) -> bool:
    assert src_channel or src_channel_id, 'Neither source channel ID nor channel object given, one is required.'
    if src_channel is None:
        assert src_channel_id
        src_channel = Channel(src_channel_id)

    assert target_playlist_id or target_playlist, 'Neither target playlist ID nor playlist object given, one is required.'
    if target_playlist is None:
        assert target_playlist_id
        target_playlist = Playlist(target_playlist_id)
    src = src_channel.get_upload_playlist(
        full_videos_only= full_videos_only,
        livestreams_only= livestreams_only,
        shorts_only= shorts_only
    )
    return add_playlist_to_playlist(src_playlist= src, target_playlist= target_playlist)


def main() -> None:
    load_dotenv()
    logging.basicConfig(level= 'INFO')
    # p = Playlist('PLSjSv6ic5w6SPHNv-8iaIeooYQtVkq3Hl')
    # v = Video('1jm2olxQigQ')
    # p.add_video(v.id)
    # p.remove_video(v.id)

    c = Channel('UCOupN4D1hLy88kkHqvXqMOQ')
    print(c.get_profile_image())
    # SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
    # creds = authorize(SCOPES)

    # youtube = build('youtube', 'v3', credentials=creds)
    # request = youtube.channels().list(part='snippet,contentDetails,statistics', mine=True)
    # response = request.execute()
    # print(json.dumps(response, indent=2))
if __name__ == "__main__":
    main()
