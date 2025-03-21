#!/usr/bin/python

import argparse
import asyncio
import os
import socket

import constants
import game


def main():
    parser = argparse.ArgumentParser(
        description="Bang Bang " + constants.VERSION,
        epilog="See the README for more information.",
        prog="bangbang",
    )
    parser.add_argument("host", help="Provide a host to bind to")
    parser.add_argument("-m", "--no-music", help="Disable music", action="store_true"),
    parser.add_argument(
        "-v",
        "--version",
        help="Print version number and exit",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-d",
        "--debug",
        help="Print debugging information to the console",
        action="store_true",
        default=False,
    )

    args = parser.parse_args()

    if args.version:
        print("Bang Bang " + constants.VERSION + "\n")

        print("Running on:\n")

        # https://docs.python.org/3/library/sys.html#sys.version
        import platform

        print("Python", platform.python_version())
        print("https://www.python.org/ \n")

        # automatically prints version upon import
        import pygame

        # I couldn't find any way to print the PyOpenGL version...
        # http://pyopengl.sourceforge.net/documentation/
        print("Made with PyOpenGL")
        print("http://pyopengl.sourceforge.net")

        return

    try:
        asyncio.run(game.main(args.host, args.no_music, args.debug))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
