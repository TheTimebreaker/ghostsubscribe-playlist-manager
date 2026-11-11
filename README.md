# GhostSubscribe Playlist Manager
## A tool for effortlessly managing ghost subscriptions and playlists on YouTube.
This tool nor any aspect associated with it is endorsed by YouTube.


## What is it
This tool was written mainly to allow you to ghost subscribe to YouTube channels, which automatically will add all new uploads of that channel to one of your playlists.

That's right! You are no longer bound by the YouTube frontpage or the glitching subscription page. With this tool you can make sure to never miss an upload ever again!


## Get started (hopefully beginner friendly!)
### Requirements (before this guide)
* The latest [release executable](https://github.com/TheTimebreaker/ghostsubscribe-playlist-manager/releases/tag/latest) of this application
* A Google account / a YouTube account

### How to install
Unfortunately, the initial setup is a few minutes of annoying work. However, it only needs to be done once.

We need to give the app credentials, so that it can do things on your behalf (e.g. adding videos to your playlists).
For that, we need to setup the Google Cloud Console.
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
11. Once downloaded, rename the file to `credentials.json` and try to run the application. You should then be able to filepick your credentials.

Now you are set up!

### How to use
On your first use (and every now and then) using this tool will require you to authorize it to Google. Whenever required, this tool will (before actually starting) open your browser, where you just need to authorize it.

The individual tools are supposed to be self-explanatory, so if something is not, feel free to [create an issue](https://github.com/TheTimebreaker/ghostsubscribe-playlist-manager/issues) and describe misunderstanding ^^

All fields regarding a Video, Playlist or Channel accept the specific ID (e.g. video ID), a full URL to the thing and handles for channels (e.g. @channel_name).
