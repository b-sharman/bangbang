I'm refactoring this project, making it asynchronous, and rewriting the network backend with websockets simultaneously. The number of lines I have changed in this effort is greater than the number of lines in the original program.

# How to play the game

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
