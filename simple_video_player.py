from __future__ import annotations
import time
import os
import logging
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, simpledialog, messagebox
from typing import Optional, TypedDict, Any
from urllib.parse import unquote, urlparse
import threading
import platform
from pynput.keyboard import Listener
from PIL import Image, ImageTk
import requests
import vlc
import yt_dlp
import centralfunctions as cf
from colors import colors
import youtube


class YouTubeMetaData(TypedDict):
    title: str
    uploader: str
    thumbnail_url: str


def get_yt_stream(youtube_url: str) -> tuple[str, str, YouTubeMetaData]:
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
        meta = YouTubeMetaData(
            title=info["title"],
            uploader=info["uploader"],
            thumbnail_url=info["thumbnail"],
        )

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
            return info["url"], info["url"], meta

        return best_video["url"], best_audio["url"], meta


def get_current_vlc_list_index(media_list_player: vlc.MediaListPlayer, playlist: vlc.MediaList) -> Optional[int]:
    current = media_list_player.get_media_player().get_media()
    if current is not None:
        for i in range(playlist.count()):
            if playlist.item_at_index(i).get_mrl() == current.get_mrl():
                return i
    return None


def wait_for_event_once(em: vlc.EventManager, event_type: Any) -> None:
    """Block until the given VLC event fires once, then return."""
    done = threading.Event()

    def _callback(_event: Any, _data: Any) -> None:
        done.set()

    em.event_attach(event_type, _callback, None)
    try:
        done.wait()
    finally:
        em.event_detach(event_type)


class PlaylistFrame(ttk.Frame):  # pylint:disable=too-many-ancestors
    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
        media_list_player: vlc.MediaListPlayer,
        playlist: vlc.MediaList,
        *args: Any,
        max_rows: int = 6,
        **kwargs: Any,
    ) -> None:
        self.parent = parent
        super().__init__(self.parent, *args, **kwargs)
        self.media_list_player = media_list_player
        self.playlist = playlist
        self.labels: list[ttk.Label] = []
        self.label_bg: Optional[str] = None
        self.more_videos_pending = False

        self.max_rows = max_rows
        self.row_height: Optional[int] = None
        self.canvas = tk.Canvas(self, height=0, bg=colors["bg-3"])
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        # Add scrollable frame inside canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<Configure>", self.resize_frame)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)  # Windows/macOS
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))  # Linux
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))  # Linux

        # Layout
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Update scrollregion when inner frame changes
        self.scrollable_frame.bind("<Configure>", lambda e: self._update_scrollregion())

        self.refresh_playlist()

        self.event_manager = self.media_list_player.event_manager()
        self.event_manager.event_attach(vlc.EventType.MediaListPlayerNextItemSet, self.refresh_playlist)

    def resize_frame(self, event: Any) -> None:
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event: Any) -> None:
        # For Windows/macOS
        self.canvas.yview_scroll(int(-2 * (event.delta / 120)), "units")

    def _update_scrollregion(self) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        if self.row_height is None and self.scrollable_frame.winfo_children():
            # Measure height of the first child (assume all rows are similar)
            first_child = self.scrollable_frame.winfo_children()[0]
            self.row_height = first_child.winfo_reqheight()

        if self.row_height:
            max_height = self.max_rows * self.row_height
            self.canvas.config(height=min(self.scrollable_frame.winfo_reqheight(), max_height))

    def refresh_playlist(self, _: Optional[Any] = None, counter: int = 0) -> None:
        """Read playlist items and display them as labels."""
        # clear existing labels
        for lbl in self.labels:
            lbl.destroy()
        self.labels.clear()

        current_index = get_current_vlc_list_index(media_list_player=self.media_list_player, playlist=self.playlist)
        for i in range(self.playlist.count()):
            if current_index and i < current_index - 1:
                continue

            media: vlc.Media = self.playlist.item_at_index(i)  # type:ignore
            if media:
                title = media.get_meta(vlc.Meta.Title) or media.get_mrl()
                artist = media.get_meta(vlc.Meta.Artist) or "Unknown Artist"
                label_text = f"{i+1}: {artist} - {title}"
                lbl = ttk.Label(self.scrollable_frame, text=label_text, anchor="w", padding=(4, 0))
                lbl.pack(fill="x", expand=True)
                self.labels.append(lbl)

                if current_index is not None and i == current_index:
                    lbl.configure(style="Selected.TLabel")
                else:
                    lbl.configure(style="TLabel")

        if self.more_videos_pending is True:
            label_text = "More videos pending... "
            lbl = ttk.Label(self.scrollable_frame, text=label_text, anchor="w", padding=(4, 0))
            lbl.pack(fill="x", expand=True)
            self.labels.append(lbl)
        if self.labels and self.canvas.winfo_manager() == "":
            self.canvas.grid(row=0, column=0, sticky="nsew")
            self.scrollbar.grid(row=0, column=1, sticky="ns")

        if counter < 4:
            self.parent.after(1000, self.refresh_playlist, None, counter + 1)


class VideoPlayer(cf.SubWindow):
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.window = tk.Toplevel(self.root)
        cf.tk_root_styles(self.window)
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        self.window.title("Video Player")
        self.window.minsize(640, 540)

        # VLC stuff
        self._instance: vlc.Instance = vlc.Instance()
        self._player: vlc.MediaPlayer = vlc.MediaPlayer()
        # playlist
        self.media_list_player: vlc.MediaListPlayer = vlc.MediaListPlayer(self._instance)
        self.playlist: vlc.MediaList = vlc.MediaList(self._instance)
        # connect playlist to the rest of the API
        self.media_list_player.set_media_player(self._player)
        self.media_list_player.set_media_list(self.playlist)

        self.volume_slider = tk.Scale(
            self.window,
            from_=0,
            to=100,
            orient="horizontal",
            label="Volume",
            command=self.set_volume,
        )
        self.volume_slider.set(self._player.audio_get_volume())  # start at current volume

        # Layout
        self.window.grid_rowconfigure(0, weight=1)  # Video row expands
        self.window.grid_columnconfigure(0, weight=1)

        # Set video frame and controls frame
        self.video_frame = ttk.Frame(self.window)
        self.video_frame.grid(row=0, column=0, sticky="nsew")
        self.placeholder_img: Optional[Image.Image] = None
        self.placeholder_photo: ImageTk.PhotoImage
        self.set_placeholder_into_video_frame()
        self.video_frame.bind("<Configure>", self.resize_placeholder)
        self.controls = ttk.Frame(self.window)
        self.controls.grid(row=1, column=0)
        self.volume_slider.grid(row=2, column=0)

        # ATB (All The Buttons)
        self.btn_width = 10
        self.mediabtn_width = 4
        self.playpause_btn = ttk.Button(
            self.controls,
            text="⏵",
            style="Media.TButton",
            command=self.toggle_play,
            width=self.mediabtn_width,
        )
        self.event_manager = self._player.event_manager()
        self.event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self.on_playing)
        self.event_manager.event_attach(vlc.EventType.MediaPlayerPaused, self.on_paused)
        self.event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self.on_paused)

        stop_btn = ttk.Button(
            self.controls,
            text="⏹",
            style="Media.TButton",
            command=self.stop,
            width=self.mediabtn_width,
        )
        next_btn = ttk.Button(
            self.controls,
            text="⏭",
            style="Media.TButton",
            command=self.next,
            width=self.mediabtn_width,
        )
        previous_btn = ttk.Button(
            self.controls,
            text="⏮",
            style="Media.TButton",
            command=self.previous,
            width=self.mediabtn_width,
        )
        add_btn = ttk.Button(
            self.controls,
            text="+ Add File",
            style="Media.TButton",
            command=self.add_file,
            width=self.btn_width,
        )
        addyt_btn = ttk.Button(
            self.controls,
            text="+ Add YT",
            style="Media.TButton",
            command=self.add_any_yt_url,
            width=self.btn_width,
        )
        self.download_btn = ttk.Button(
            self.controls,
            text="Download",
            style="Media.TButton",
            command=self.send_to_downloader,
            width=self.btn_width,
        )

        previous_btn.pack(side="left", padx=5, pady=5)
        self.playpause_btn.pack(side="left", padx=5, pady=5)
        next_btn.pack(side="left", padx=5, pady=5)
        stop_btn.pack(side="left", padx=5, pady=5)
        add_btn.pack(side="left", padx=5, pady=5)
        addyt_btn.pack(side="left", padx=5, pady=5)
        self.download_btn.pack(side="left", padx=5, pady=5)

        self.playlist_frame = PlaylistFrame(self.window, self.media_list_player, self.playlist)
        self.playlist_frame.grid(row=3, column=0, sticky="ew")

        self._embed_vlc()
        self.media_keys()
        self.print_that_shit()

    def set_volume(self, val: str) -> None:
        volume = int(val)
        self._player.audio_set_volume(volume)

    def on_close(self) -> None:
        if hasattr(self, "media_list_player"):  # make sure the VLC player exists
            self.media_list_player.stop()
        super().on_close()

    def media_keys(self) -> None:
        def on_press(key: Any) -> None:
            if str(key) == "Key.media_play_pause":
                self.toggle_play()
            elif str(key) == "Key.media_next":
                self.next()
            elif str(key) == "Key.media_previous":
                pass  # print('yeet3')# previous key was pressed

        listener_thread = Listener(on_press=on_press, on_release=None)
        listener_thread.start()

    def set_placeholder_into_video_frame(self) -> None:
        if self.placeholder_img is None:
            self.placeholder_img = Image.open("assets/video_placeholder.jpg")
            print("yeet")
        self.placeholder_photo = ImageTk.PhotoImage(self.placeholder_img)
        self.placeholder_label = ttk.Label(self.video_frame, image=self.placeholder_photo)
        self.placeholder_label.place(relx=0.5, rely=0.5, anchor="center")  # center it

    def resize_placeholder(self, event: Any) -> None:
        # Original image size
        assert self.placeholder_img
        orig_w, orig_h = self.placeholder_img.size
        frame_w, frame_h = event.width, event.height

        # Compute scaling factor to fit inside the frame while keeping aspect ratio
        scale = min(frame_w / orig_w, frame_h / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        # Resize
        resized = self.placeholder_img.resize((new_w, new_h), Image.Resampling.BILINEAR)
        self.placeholder_photo = ImageTk.PhotoImage(resized)  # keep reference
        self.placeholder_label.config(image=self.placeholder_photo)

    def print_that_shit(self) -> None:
        print("=" * 20)
        for i in range(self.playlist.count()):
            fp = self.playlist.item_at_index(i).get_mrl()
            fp_readable = unquote(urlparse(fp).path)
            print(i, fp_readable)
        self.playlist_frame.refresh_playlist()

    def _embed_vlc(self) -> None:
        handle = self.video_frame.winfo_id()
        system = platform.system()
        if system == "Windows":
            self._player.set_hwnd(handle)
        elif system == "Linux":
            self._player.set_xwindow(handle)
        elif system == "Darwin":  # macOS
            self._player.set_nsobject(handle)
        else:
            raise RuntimeError(f"Unsupported OS: {system}")

    # Control methods
    def toggle_play(self) -> None:
        if self.media_list_player.is_playing():
            self.media_list_player.pause()
        else:
            self.media_list_player.play()
            self.placeholder_label.place_forget()

    def on_playing(self, _event: Any) -> None:
        self.root.after(0, lambda: self.playpause_btn.config(text="⏸"))

    def on_paused(self, _event: Any) -> None:
        self.root.after(0, lambda: self.playpause_btn.config(text="⏵"))

    def stop(self) -> None:
        self.media_list_player.stop()
        self.set_placeholder_into_video_frame()
        self.print_that_shit()

    def next(self) -> None:
        self.media_list_player.next()
        self.print_that_shit()
        self.download_btn.configure(style="Media.TButton")

    def previous(self) -> None:
        self.media_list_player.previous()
        self.print_that_shit()
        self.download_btn.configure(style="Media.TButton")

    def send_to_downloader(self) -> None:
        current_index = get_current_vlc_list_index(media_list_player=self.media_list_player, playlist=self.playlist)
        if current_index is None:
            messagebox.showerror(
                "Error - Current playlist index could not be determined",
                message="Download could not be initiated.\nReason: Finding of current playlist position failed.",
            )
        media = self.playlist.item_at_index(current_index)
        url = str(media.get_meta(vlc.Meta.Description))
        if url.startswith("streamed:"):
            match "JDownloader2":
                case "JDownloader2":
                    result = self._download_jdownloader2(url)

            if result is True:
                self.download_btn.configure(style="Success.Media.TButton")
            else:
                self.download_btn.configure(style="Failure.Media.TButton")
        else:
            messagebox.showerror(
                "Error - Could not download file",
                message="The current video could not be downloaded, since it is not a streamed video.\n"
                "Local files cannot be downloaded again.\n"
                "If you believe that this is a mistake, please open an issue on GitHub.",
            )

    def _download_jdownloader2(self, url: str) -> bool:
        logging.info("Downloading %s via JDownloader2...", url)
        jdurl = f"http://127.0.0.1:9666/flash/add?urls={url}&source=ghostsub_videoplayer"
        try:
            res = requests.post(jdurl, timeout=10)
            if res.status_code == 200:
                logging.info("Downloading %s via JDownloader2... SUCCESS!", url)
                return True
            error_msg = f"Downloading {url} via JDownloader2... Unsuccessful! Status code: {res.status_code} . Text: {res.text}."
            logging.error(error_msg)
            messagebox.showerror("Error - Download via JDownloader2 unsuccessful", message=error_msg)
            return False
        except requests.exceptions.Timeout:
            error_msg = f"Downloading {url} via JDownloader2... Unsuccessful! Timeout"
            logging.error(error_msg)
            messagebox.showerror("Error - Download via JDownloader2 unsuccessful", message=error_msg)
            return False

    def add_file(self) -> None:
        filepath = filedialog.askopenfilename(
            title="Select a video file",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mkv"),
                ("Audio files", "*.mp3 *.aac *.flac"),
                ("All files", "*.*"),
            ],
        )
        if filepath:
            playlist_was_empty = self.playlist.count() == 0
            media = vlc.Media(self._instance, filepath)
            media.set_meta(vlc.Meta.Description, "")
            self.playlist.add_media(media)
            if playlist_was_empty:
                self.toggle_play()
            self.print_that_shit()

    def add_any_yt_url(self) -> None:
        """Opens up a dialog box that asks for a youtube link.
        Will attempt to add the video, all video of the youtube playlist, or all channel uploads, depending on URL type.
        """
        playlist_buffer = 10

        def inner(obj: youtube.Youtube) -> None:
            if isinstance(obj, youtube.Channel):  # pylint:disable=possibly-used-before-assignment
                inner(obj.get_upload_playlist())
            elif isinstance(obj, youtube.Playlist):
                self.playlist_frame.more_videos_pending = True
                em = self.media_list_player.event_manager()
                for video in obj.yield_elements(part=["snippet"]):
                    video_id = video["snippet"]["resourceId"]["videoId"]
                    youtube_url = f"https://youtube.com/watch?v={video_id}"

                    current_index = get_current_vlc_list_index(self.media_list_player, self.playlist)
                    current_length = self.playlist.count()
                    while current_index is not None and current_index + playlist_buffer < current_length:
                        print(time.time(), "waiting for VLC to move to next item...")
                        wait_for_event_once(em, vlc.EventType.MediaListPlayerNextItemSet)

                        # after VLC advanced, update values and re-check
                        current_index = get_current_vlc_list_index(self.media_list_player, self.playlist)
                        current_length = self.playlist.count()

                    self._add_yt_video(youtube_url)
                self.playlist_frame.more_videos_pending = False
            elif isinstance(obj, youtube.Video):
                self._add_yt_video(obj.url)
            else:
                print("why")
            self.print_that_shit()

        yturl = simpledialog.askstring(parent=self.window, title="Enter a YouTube URL:", prompt="URL:")
        if yturl:
            try:
                obj = youtube.Youtube().parse_any_url(yturl)
            except youtube.SkippableException:
                messagebox.showerror(
                    "Error - Could not parse URL",
                    message=f"The url you provided:\n{yturl}\ncould not be parsed.\n\n"
                    "This could be an issue with this program or with YouTube's API.",
                )
                return
            threading.Thread(target=inner, args=(obj,)).start()

    def _add_yt_video(self, url: str) -> None:
        """Inner function that takes a youtube video link and adds it.

        Args:
            url (str): Video URL
        """
        videourl, audiourl, metadata = get_yt_stream(url)
        playlist_was_empty = self.playlist.count() == 0
        media = vlc.Media(self._instance, videourl)
        media.add_option(f":input-slave={audiourl}")
        media.set_meta(vlc.Meta.Title, metadata["title"])
        media.set_meta(vlc.Meta.Artist, metadata["uploader"])
        media.set_meta(vlc.Meta.Description, f"streamed:{url}")
        self.playlist.add_media(media)
        if playlist_was_empty:
            self.toggle_play()


def main() -> None:
    root = tk.Tk()
    cf.ttk_styles(root)
    cf.tk_root_styles(root)
    root.withdraw()
    VideoPlayer(root)
    root.mainloop()


if __name__ == "__main__":
    print(os.getenv("THEME"))
    main()
