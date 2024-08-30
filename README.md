# State of the project
I mostly finished refactoring a horrible pile of spaghetti written by my former self into something plausibly maintainable and respectable. However, in order to preserve compatibility with the old hardware the project was originally designed for, I retained some legacy decisions (for example, the game doesn't work on Wayland), and I eventually realized that the cross-compatibility necessary would mean I would be best off writing a new frontend with some sort of web technology—a massive effort which caused me to abandon the project.

As such, **there are some unfinished pieces** that I would consider embarrassing were this project declared to be production-ready. There's some improvement left to do in the typing, and I ought to create a virtual environment rather than relying on the user to install dependencies manually. Also, a TCP protocol like WebSockets was an odd choice for a video game, and switching to something else would mean rewriting most of the network code.

Despite this, I still think it's a good project to keep around because it shows what my other projects don't:
- I can architect projects larger than the hackathons I usually post.
- I am interested in—and am capable of—more than JavaScripty web stuff.

Below is the README in the state when I last actively maintained the project.

---

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
