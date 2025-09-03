from __future__ import annotations
import tkinter as tk
from typing import Optional, TypedDict, Any
from tkinter import filedialog, simpledialog
from urllib.parse import unquote, urlparse
import platform
import vlc
import yt_dlp
from main import SubWindow, tk_root_styles, ttk_styles
import youtube

class YouTubeMetaData(TypedDict):
    title:str
    uploader:str
    thumbnail_url:str

def get_yt_stream(youtube_url:str) -> tuple[str,str,YouTubeMetaData]:
    """
    Given a YouTube URL, returns a tuple of (best_video_url, best_audio_url)
    suitable for VLC input-slave playback.
    """
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "quiet": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        meta = YouTubeMetaData(title = info['title'], uploader= info['uploader'], thumbnail_url= info['thumbnail'])

        # If DASH, 'formats' will contain separate video/audio streams
        best_video = None
        best_audio = None

        for f in info.get("formats", []):
            if f.get("vcodec") != "none":
                height = f.get("height") or 0
                if best_video is None or height > (best_video.get("height") or 0):
                    best_video = f
            if f.get("acodec") != "none":
                abr = f.get("abr") or 0
                best_abr = best_audio.get("abr") if best_audio else 0
                if best_audio is None or abr > best_abr:
                    best_audio = f

        if not best_video or not best_audio:
            # fallback if no DASH detected
            return info['url'], info['url'], meta

        return best_video['url'], best_audio['url'], meta


class PlaylistFrame(tk.Frame):
    def __init__(
            self,
            parent:tk.Tk|tk.Toplevel,
            media_list_player: vlc.MediaListPlayer,
            playlist: vlc.MediaList,
            *args:Any,
            **kwargs:Any
        ) -> None:
        self.parent = parent
        super().__init__(self.parent, *args, **kwargs)
        self.media_list_player = media_list_player
        self.playlist = playlist
        self.labels:list[tk.Label] = []

        self.refresh_playlist()

        self.event_manager = self.media_list_player.event_manager()
        self.event_manager.event_attach(vlc.EventType.MediaListPlayerNextItemSet, self.refresh_playlist)

    def refresh_playlist(self, _:Optional[Any] = None, counter:int = 0) -> None:
        """Read playlist items and display them as labels."""
        # clear existing labels
        for lbl in self.labels:
            lbl.destroy()
        self.labels.clear()

        for i in range(self.playlist.count()):
            media:vlc.Media = self.playlist.item_at_index(i) #type:ignore
            if media:
                title = media.get_meta(vlc.Meta.Title) or media.get_mrl()
                artist = media.get_meta(vlc.Meta.Artist) or 'Unknown Artist'
                lbl = tk.Label(self, text=f"{artist} - {title}", anchor="w", padx=4)
                lbl.pack(fill="x", pady=1)
                self.labels.append(lbl)
        self.update_current()

        if counter < 10:
            self.parent.after(10, self.refresh_playlist, None, counter+1)
        elif counter < 12:
            self.parent.after(1000, self.refresh_playlist, None, counter+1)
    def update_current(self, _:Optional[Any] = None) -> None:
        """Highlight currently playing item."""
        def get_current_index() -> Optional[int]:
            current = self.media_list_player.get_media_player().get_media()
            for i in range(self.playlist.count()):
                if self.playlist.item_at_index(i).get_mrl() == current.get_mrl():
                    return i
            return None
        current_index = get_current_index()
        if not current_index is None:
            for i, lbl in enumerate(self.labels):
                if i == current_index:
                    lbl.config(bg="lightblue")
                else:
                    lbl.config(bg = lbl.master.cget("bg"))
        


class VideoPlayer(SubWindow):
    def __init__(self, root:tk.Tk) -> None:
        self.root = root
        self.window = tk.Toplevel(self.root)
        tk_root_styles(self.window)
        self.window.protocol('WM_DELETE_WINDOW', self.on_close)
        self.window.title('Video Player')
        self.window.minsize(1000, 1000)


        # VLC stuff
        self.instance = vlc.Instance()
        self.player = vlc.MediaPlayer()
        #playlist
        self.m1_player = vlc.MediaListPlayer(self.instance)
        self.playlist = vlc.MediaList(self.instance)
        # connect playlist to the rest of the API
        self.m1_player.set_media_player(self.player)
        self.m1_player.set_media_list(self.playlist)


        # Layout
        self.window.grid_rowconfigure(0, weight=1)   # Video row expands
        self.window.grid_columnconfigure(0, weight=1)

        # Set video frame and controls frame
        self.video_frame = tk.Frame(self.window, highlightbackground='red', highlightthickness=2)
        self.video_frame.grid(row=0, column=0, sticky="nsew")
        self.controls = tk.Frame(self.window)
        self.controls.grid(row=1, column=0, sticky="ew")

        #ATB (All The Buttons)
        # self.play_btn = tk.Button(self.controls, text="⏵ Play", command=self.play)
        # self.pause_btn = tk.Button(self.controls, text="⏸ Pause", command=self.pause)
        self.playpause_btn = tk.Button(self.controls, text="⏵ Play", command=self.play)

        stop_btn = tk.Button(self.controls, text="⏹ Stop", command=self.stop)
        next_btn = tk.Button(self.controls, text="⏭ Next", command=self.next)
        add_btn = tk.Button(self.controls, text="+ Add", command=self.add_file)
        addyt_btn = tk.Button(self.controls, text="+ YT Video", command=self.add_yt_url)
        self.playpause_btn.pack(side="left", padx=5, pady=5)
        stop_btn.pack(side="left", padx=5, pady=5)
        next_btn.pack(side="left", padx=5, pady=5)
        add_btn.pack(side="left", padx=5, pady=5)
        addyt_btn.pack(side="left", padx=5, pady=5)


        self.playlist_frame = PlaylistFrame(self.window, self.m1_player, self.playlist)
        self.playlist_frame.grid(row=2, column=0, sticky="ew")

        self._embed_vlc()
        self.print_that_shit()
    def print_that_shit(self) -> None:
        print('='*20)
        for i in range(self.playlist.count()):
            fp = self.playlist.item_at_index(i).get_mrl()
            fp_readable = unquote(urlparse(fp).path)
            print(i, fp_readable)
        self.playlist_frame.refresh_playlist()
    def _embed_vlc(self) -> None:
        handle = self.video_frame.winfo_id()
        system = platform.system()
        if system == "Windows":
            self.player.set_hwnd(handle)
        elif system == "Linux":
            self.player.set_xwindow(handle)
        elif system == "Darwin": #macOS
            self.player.set_nsobject(handle)
        else:
            raise RuntimeError(f"Unsupported OS: {system}")

    # Control methods
    def play(self) -> None:
        self.m1_player.play()
        self.playpause_btn.config(text = '⏸ Pause', command=self.pause)
        self.print_that_shit()

    def pause(self) -> None:
        self.m1_player.pause()
        self.playpause_btn.config(text = '⏵ Play', command=self.play)
        self.print_that_shit()

    def stop(self) -> None:
        self.m1_player.stop()
        self.print_that_shit()

    def next(self) -> None:
        self.m1_player.next()
        self.print_that_shit()

    def add_file(self) -> None:
        filepath = filedialog.askopenfilename(
            title = 'Select a video file',
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mkv"),
                ("Audio files", "*.mp3 *.aac *.flac"),
                ("All files", "*.*")
            ]
        )
        if filepath:
            playlist_was_empty = self.playlist.count() == 0
            media = vlc.Media(self.instance, filepath)
            self.playlist.add_media(media)
            if playlist_was_empty:
                self.play()
            self.print_that_shit()
    def add_yt_url(self) -> None:
        yturl = simpledialog.askstring(
            parent=self.window,
            title= 'Enter a YouTube URL:',
            prompt = 'URL:'
        )
        if yturl:
            obj = youtube.Youtube().parse_any_url(yturl)
            if isinstance(obj, (youtube.Channel, youtube.Playlist)):
                print('iterable')
            elif isinstance(obj, youtube.Video):
                self._add_video_url(obj.url)
            else:
                print('why')
            self.print_that_shit()
    def _add_video_url(self, yturl:str) -> None:
        videourl, audiourl, metadata = get_yt_stream(yturl)
        playlist_was_empty = self.playlist.count() == 0
        media = vlc.Media(self.instance, videourl)
        media.add_option(f":input-slave={audiourl}")
        media.set_meta(vlc.Meta.Title, metadata["title"])
        media.set_meta(vlc.Meta.Artist, metadata["uploader"])
        self.playlist.add_media(media)
        if playlist_was_empty:
            self.play()



def main() -> None:
    # youtube.Youtube() #verifies credentials
    root = tk.Tk()
    ttk_styles(root)
    root.withdraw()
    VideoPlayer(root)
    root.mainloop()
if __name__ == '__main__':
    main()