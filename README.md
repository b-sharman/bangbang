In 2023, I successfully refactored what used to be an old middle school project
into something plausibly maintainable and respectable. However, in order to
preserve compatibility with old hardware, I retained some legacy decisions (for
example, the game doesn't work on Wayland), and I eventually realized that the
cross-compatibility I needed would require me to port the frontend to WebGL or
even rewrite it from scratch—a massive effort which caused me to shift my
attention to other projects.

That's why I feel obliged to point out the missing pieces that I wouldn't want
in a finished project: unenforced typing, no unit tests, no dependency
management or `pyproject.toml`. Also, a TCP protocol like WebSockets is an odd
choice for a non-web video game.

Despite this, I still solved a lot of interesting problems while rewriting it,
and I don't feel like trying to bury it because it is one of my more ambitious
completed projects. If you want to try it out, follow the steps below:

1. Install these dependencies:
* [aioconsole](https://aioconsole.readthedocs.io/en/latest/)
* [PyOpenGL](https://pyopengl.sourceforge.net/)
* [pygame](https://www.pygame.org/news)
* [websockets](https://websockets.readthedocs.io/en/stable/)

2. Clone the `refactor` branch:
```sh
$ git clone https://github.com/b-sharman/bangbang.git # for HTTPS
```
```sh
$ git clone git@github.com:b-sharman/bangbang.git # for SSH
```

3. Start a server:
```sh
$ cd bangbang/bangbang
$ python server.py
```

4. Then start client(s) using the IP address listed by the server:
```sh
$ ./bangbang [ip]
```
Note that the game currently only works over LAN.

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
