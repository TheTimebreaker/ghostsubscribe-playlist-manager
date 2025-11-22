# GhostSubscribe Playlist Manager
## A tool for effortlessly manage ghost subscriptions and playlists on YouTube.
This tool nor any aspect associated with it is endorsed by YouTube.




# What is it
This tool was written mainly to allow you to ghost subscribe to YouTube channels, which automatically will add all new uploads of that channel to one of your playlists.

That's right! You are no longer bound by the YouTube frontpage or the glitching subscription page. With this tool you can make sure to never miss an upload ever again!


# What can it do
When starting this program, you can choose between the different tools provided (more to come <sup>tm</sup>):
* Add to Playlist
    * Allows you to add anything (a video, a playlist or an entire channel) to one of your playlists.
* Auto adder
    * The main management hub for your ghost subscriptions. Named like this because it automatically adds stuff compared to the manual "Add to Playlist" feature.
* Remove Playlist entries up to index
    * A terrible name for a tool that will remove all videos in a given playlist up until (and including) the index provided. Useful whenever you just binged one of your playlists to video 69 and don't want to remove the watched videos all by yourself.
* Simple Video Player
    * (Currently disfunctional due to recent YouTube changes that are causing issues that I wasn't able to fix) A very barebones video player that can play local files as well as YouTube videos. Due to its simplicity, this player is less laggy and faster compared to the official YouTube player (atleast for larger playlists, which seem to be causing the website a lot of trouble handling).

# Get started (hopefully beginner friendly!)
## Requirements (before this guide)
* Python 3.13 (grab the latest release from [here](https://www.python.org/downloads))
    * Depending on your installation method, you will need to type different things into your command line to access python features. For ease of use, <strong>I recommend installing pylauncher together with your python installation.</strong>.
    * Since there are a few different commands possible, I will be listing some alternative commands where necessary.
* A Google account / a YouTube account

## How to install
Since this is still in very active development and since I have no idea how this GitHub stuff actually works, this is still a bit annoying.
1. Download the entire source code of this repository by clicking [here](https://github.com/TheTimebreaker/ghostsubscribe-playlist-manager/archive/refs/heads/main.zip).
2. Extract the zip and place the folder `ghostsubscribe-playlist-manager-main` to whereever you see fit.
    * Don't put the extracted folder into protected folders like Windows' `Program Files` folders.
3. Open the folder in your command line tool of choice.
    * If you are unsure how to do this, search for `<operating system> command line navigate to specific folder` on the internet.
    * To test whether you are in the correct folder, type in `py main.py`, `python main.py`, or `python.exe main.py`. If you are in the correct folder, the program should immediately exit due to a `ModuleNotFoundError`. Don't worry about what that means, cuz we will prevent it from happening again in the next step.
4. Create a virtual environment by running the command `py -m venv .venv`
    * Alternative commands:
    * `python -m venv .venv`
    * `python.exe -m venv .venv`
5. Activate a virtual environment by running the command `.venv\Scripts\activate`
    * Depending on your command line, this should now display an indication that you are using a virtual environment somewhere in your command line window.
6. Install the required modules by running the command `py -m pip install -r requirements.txt`.
    * Alternative commands:
    * `python -m pip install -r requirements.txt`
    * `python.exe -m pip install -r requirements.txt`
    * `pip install -r requirements.txt`

This will setup python so that it can function properly.
Next, we need to give the code credentials, so that it can add things to your own playlists.
For that, we need to setup the Google Cloud Console once.
1. Visit the [Google Cloud Console](https://console.cloud.google.com) and log into your account.
2. Open the `Project Picker` in the top left corner.
3. Click `New Project`, give it an appropriate name, select `No organisation` and click `Create`.
    * An example name would be `GhostSubscribe`.
4. Open the `Project Picker` again and choose your newly created project.
5. Go to the search bar, enter `YouTube` and select the entry `YouTube Data API v3`.
6. Click the `Enable` button.
7. Once enabled, you should be kicked back to the main page of the project.
8. Click `Credentials`, `Create credentials`, `Oauth client ID`.
    * You'll probably need to configure a Consent screen before Google lets you actually create the credentials.
    * Enter the name of the app (`GhostSubscribe`), the email adress of your account as the User support email.
    * For `Audience`, select `External`.
    * For `Contact Information`, enter your email adress again.
    * Agree to the user agreements and create it.
9. Choose `Desktop app` as the application type, `GhostSubscribe` as the Name and hit `Create`.
10. Once it is created, press the `Download JSON` button.
11. Once downloaded, rename the file to `credentials.json` and move it into the main folder of this tool.

Now you are set up!

## How to use
On your first use (and every now and then) using this tool will require you to authorize it to Google. Whenever required, this tool will (before actually starting) open your browser, where you just need to authorize it.

The individual tools are supposed to be self-explanatory, so if something is not, feel free to [create an issue](https://github.com/TheTimebreaker/ghostsubscribe-playlist-manager/issues) and describe misunderstanding ^^

All fields regarding a Video, Playlist or Channel accept the specific ID (e.g. video ID), a full URL to the thing and handles for channels (e.g. @channel_name).

### Add to playlist
The top half is dedicated to selecting which type of content (`Video`, `Playlist` or `Channel Uploads`) you want to add to a playlist. Choosing `Channel Uploads` will display a selector, where you can choose to add all videos or a subset of videos.

The bottom half allows you to specify the target playlist.

All selected fields will be checked for completeness and will be verified before anything else is done. This will prevent sending broken requests to YouTube and using your API quota unnecessarily. After clicking `Confirm`, you need to wait for a moment until the tool has finished adding everything, after which you will be informed of a success.

### Auto adder
TODO