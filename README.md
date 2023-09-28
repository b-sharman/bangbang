This is project is several years old, and I'm refactoring it, making it asynchronous, and rewriting the network backend with websockets simultaneously. Therefore, it's currently unplayable...

# How to play the game

It's not currently playable (see above), but here's how you can test it.

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

6. The controls aren't currently documented, but you can try to figure them out by looking at the `KEYMAP` in `constants.py`.
