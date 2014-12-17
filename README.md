torrentcatcher
===========
###Requirements
* transmission-remote

###Description
Takes torrent or magnet links from rss feeds you provide, parses them and sends them to transmission via the transmission-remote command line utility.
###Installation and Usage
To install this for your personal use run these commands:
```
$ git clone https://github.com/archangelic/torrentcatcher
$ cd torrentcatcher/
$ ./setup.py install
$ torrentcatcher
```
`setup.py` will download and install any unmet python dependencies.  
`torrentcatcher` will start the utility, and give you an error about there being no feeds.  
This will also check for the relevant data files, and, if they do not exist, will create them in the `.torrentcatcher` in your home directory.  

The `trconfig` file will be in there with some default values already filled in:
```
hostname = localhost
port = 9091
require_auth = False
username = ""
password = ""
download_directory = ""
```
Fill in the config file with the relevant information to access your transmission rpc session. Make sure to set `require_auth` to `True` if your transmission rpc requires a username and password.  
The `download_directory` value will override your transmission session's global download directory for torrents gathered by torrentcatcher.

`torrentcatcher.py -h` will reveal all available options and their descriptions.
