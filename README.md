This is a very old project that I've recently (2023–2024) refactored into a
pretty nice codebase, and probably the largest personal project I have ever
worked on.

## How can I try it?

By installing it locally.

I haven't gotten around to properly packaging this thing, so for now, just
install from the `requirements.txt`.

1. Clone the repository:
```sh
$ git clone https://github.com/b-sharman/bangbang.git # for HTTPS
```
```sh
$ git clone git@github.com:b-sharman/bangbang.git # for SSH
```

2. Make and activate a virtual environment:
```sh
$ cd bangbang
$ python -m venv .venv
$ source .venv/bin/activate
```

3. Install dependencies:
```sh
$ pip install requirements.txt
```

3. Start a server:
```sh
$ cd bangbang
$ python server.py
```

4. Then, from another terminal or another computer on the same LAN, start
   client(s) using the IP address listed by the server:
```sh
$ python bangbang.py [ip]
```

5. Type `start` from the server instance.

## Controls

|Keypress|Action|
|-|-|
|`up`|accelerate|
|`down`|decelerate|
|`s`|stop (if speed is sufficiently close to zero)|
|`left`|turn base and turret left together|
|`right`|turn base and turret right together|
|`shift`+`left`|turn the turret left|
|`shift`+`right`|turn the turret right|
|`ctrl`+`left`|turn the base left|
|`ctrl`+`right`|turn the base right|
|`t`|align the turret with the base|
|`ctrl`+`t`|align the base with the turret|
|`space`|fire a shell|
|`b`|lay a mine|
|`ESC`|force quit|
|`f`|print current FPS to console|
