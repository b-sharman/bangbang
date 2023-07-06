"""
This is a server. It will send messages back and forth between the clients.

Call this on only one computer.
"""

# Add compatibilty for Python 2.6. Wow, dat old.
# "The features recognized by Python 2.6 are unicode_literals, print_function, absolute_import,
# division, generators, nested_scopes and with_statement. generators, with_statement, nested_scopes
# are redundant in Python version 2.6 and above because they are always enabled."
# https://docs.python.org/2.7/reference/simple_stmts.html#future
# Edit: I don't think we want support for <2.7 if possible, this would really be nasty
# I got an error with unicode_laterals:
#     from __future__ import division, absolute_import, print_function, unicode_laterals
# SyntaxError: future feature unicode_laterals is not defined

from __future__ import division, absolute_import, print_function

import sys
import random
import time
from math import sqrt
from weakref import WeakKeyDictionary

import numpy as np

from bbutilities import *
from version import __version__

sys.path.append("../PodSixNet")

from PodSixNet.Server import Server
from PodSixNet.Channel import Channel

NAME_PLACEHOLDER = "An unidentified player"      

class ClientChannel(Channel):
    """ This is the server representation of a single connected client. """

    def __init__(self, *args, **kwargs):
        Channel.__init__(self, *args, **kwargs)
        self.name = NAME_PLACEHOLDER
        self.won = False # did we win?
        
    def Close(self):
        self._server.DelPlayer(self)
        
    def Network_test(self, data):
        """ Used by the automatic server-finding function. """
        
        if data["message"] != MESSAGE:
            print("Eh. A fake dude is up to hacking.")
            return
        
        print("Yes! it was my first love!")
        self.Send({"action": "foundit", "servername": self._server.name})
        self.Pump()
        time.sleep(0.1)
        print("sending out a beam of hope to you...")

    def Network_bangbangtest(self, data):
        """ Called by the client to ensure that it's a real connection """

        # Edit (07/23/18): WHAT IS THIS FOR????
        # Edit (01/11/18): Still no idea what this is
        # Edit (12/25/17): No idea what this is, it's just a pass?????

        #test = data["bangbangtest"]
        pass

    def Network_name(self, data):
        self.name = data["name"]
        print(self.name + " has joined the game.")
        self._server.SendPlayerStatus(self.name, "joined")
        
        self.Send({"action": "naturalobjs",
                     "hillposes": self._server.hillposes,
                     "treeposes": self._server.treeposes
                     })
        self.Pump()

        time.sleep(0.001) # Give some delay to process the information before we go on

        self._server.Pump()

    def Network_attributes(self, data):
        """ Get the attributes of the player. """

        pos = data["pos"]
        bout = data["bout"]
        tout = data["tout"]

        # We need to pool this in the hat.
        if data["card"]:
            self.card = data
            self._server.AddToHat(self.card)
            self._server.CheckGameStart()

        else:
            # Send attributes to all other players
            self._server.SendToAll({"action": "recvattr",
                                    "name": self.name, # For Player recognition
                                    "pos": data["pos"],
                                    "bout": data["bout"],
                                    "tout": data["tout"],
                                    "bright": data["bright"],
                                    "tangle": data["tangle"],
                                    "bangle": data["bangle"],
                                    "color": data["color"],
                                    "speed": data["speed"],
                                    "keys": data["keys"]
                                    })

    def Network_shoot(self, data):
        self._server.SendToAll({"action": "makebullet",
                                "pos": data["pos"],
                                "tout": data["tout"],
                                "tangle": data["tangle"],
                                "name": self.name,
                                "id": data["id"]})
        
    def Network_mine(self, data):
        self._server.SendToAll({"action": "makemine",
                                "name": data["name"],
                                "pos": data["pos"],
                                "color": data["color"],
                                "id": data["id"]})

    def Network_dead(self, data):
        self._server.SendToAll({"action": "recvdead",
                                "pos": data["pos"],
                                "color": data["color"],
                                "name": self.name})

    def Network_won(self, data):
        self._server.SendToAll({"action": "recvwon",
                                "name": self.name})
        
    def Network_minehit(self, data):
        self._server.SendToAll({"action": "recvmine",
                                "name": data["name"],
                                "id": data["id"]})

    def Network_tankhit(self, data):
        self._server.SendToAll({"action": "recvhit",
                                "id": data["id"],
                                "name": data["name"]
                                })


class BangBangServer(Server):
    channelClass = ClientChannel

    def __init__(self, *args, **kwargs):
        global HW

        Server.__init__(self, *args, **kwargs)
        self.players = WeakKeyDictionary()
        print("Welcome to BangBang " + __version__)
        # We are going to ask how many players are expected
        # Although this might be annoying, it allows a simple
        # input for the clients.
        host = kwargs["localaddr"][0]
        port = kwargs["localaddr"][1]
        
        # try to read the existing server name
        try:
            reader = open("servername", "r") # this will raise IOError if servername doesn't exist
        except IOError:
            # Now we have to ask the user for the name and then write it to the file
            self.name = input23("Your name (leave blank to skip): ")
            writer = open("servername", "w")
            writer.write(self.name)
            writer.close()
        else:
            # supposedly, if the try statement worked without raising an exception,
            # then we should get here. We finish reading the server name and don't
            # have to bug the user.
            self.name = reader.read().strip()
            reader.close()
            
        self.num_players = ask_number("How many players are you expecting? ")
        # This print statement is a lie. The server was launched up at Server.__init__(self, *args, **kwargs) but we don't say it's launched until now.
        print("Server launched on " + str(host) + ":" + str(port))

        HW = HW_CONST * int(round(sqrt(2.0 * self.num_players)))
        
        self.game_started = False
        self.hat = []

        # Find natural object positions
        self.hillposes, self.treeposes = naturalobj_poses(self.num_players, HW)

    def Connected(self, channel, addr):
        self.AddPlayer(channel)
        print("found a connection")

    def AddPlayer(self, player):
        if len(self.players) < self.num_players:
            self.players[player] = True
            if len(self.players) == 1:
                self.firstplayer = player

    def AddToHat(self, data):
        self.hat.append(data)

    def CheckGameStart(self):

        # Quit if two players have the same name
        for player in self.players:
            
            if ([p.name for p in self.players].count(player.name) > 1) and player.name != NAME_PLACEHOLDER:
                message = "More than one player named " + \
                          p.name + "."
                print("Fatal error:", message)
                self.SendToAll({"action": "error", "error": message})
                self.Pump()
                exit()

        # waiting_for = self.num_players - len(self.players)
        # if not waiting_for and NAME_PLACEHOLDER not in [p.name for p in self.players]: # All players are ready!
        if len(self.hat) == self.num_players: # All players have assigned their attribute cards to the hat
            self.game_started = True

            # Find good tank positions
            # Make sure that they aren't too close to each other!
        
            # btw it was raining when I wrote this
            # Calculate the minimum distance:
            MIN_DIST = ((2 * sqrt(2)) / 4) * HW - 10 # I think the units are in OGL units, which are very roughly a meter
        
            # First, we need to find the first player's position.
            firstpos = random_tankpos(self.hillposes, HW)
            poses = [firstpos]
            poses_dict = {self.firstplayer.name: a2tf(firstpos)}

            temp_players = self.players.copy()
            del temp_players[self.firstplayer]
            for player in temp_players:

                # Next, we will keep trying until we find one that works
                # We will keep a timer, though, to avoid an infinite loop
                # so if we can't find a valid pos within 5 seconds we will give up
                starttime = time.time()
                valid = False
                while not valid:

                    # Make a position
                    postry = random_tankpos(self.hillposes, HW)

                    # It's true until proven false.
                    valid = True

                    for pos in poses: # check every tank

                        # Is it far away enough from another tank?
                        if mag(pos - postry) <= MIN_DIST:
                            
                            valid = False
                            
                    if valid:
                        # If we get here, it means that the pos worked out!
                        validpos = postry

                    # Stop after 5 seconds of searching to avoid infinite loop
                    if time.time() - starttime >= 5.0:
                        print("Couldn't find a good spawn point.\nSome people will end up being close together.")

                        # I don't think I should put a break here, because it might break the parent for-loop
                        # so we will set valid to true, even though it's not
                        # and that will end the while loop, but not the for loop
                        # which is exactly what we want
                        validpos = postry
                        valid = True

                # We don't wanna add to poses while we're looping through it, so we'll put this line here
                poses.append(validpos)
                
                # Format validpos for PSN
                # for whatever reason it can't send special object types, and sometimes not even a tuple...
                # WHAT IS GOING ON HERE?
                # In send_attributes I have to send posx, posy, posz, etc.. and it takes up a ton of space
                # I don't know why PSN can't handle this, but it's bloody annoying
                poses_dict[player.name] = a2tf(validpos)
                
            # Send Start signal, along with a picture of the cards in the hat
            self.SendToAll({"action": "startgame",
                            "hat": self.hat,
                            "num_players": self.num_players,
                            "poses_dict": poses_dict})
            self.Pump()

    def DelPlayer(self, player):

        #if player.name != NAME_PLACEHOLDER:
        print(player.name + " is leaving the game.")

        del self.players[player]
        self.SendPlayerStatus(player.name, "left")

        # If all players have left the game and if the game has already
        # started, then the game is over.
        if len(self.players) <= 0 and self.game_started:
            print("The game has ended.")
            exit()

    def SendPlayerStatus(self, name, status):
        """ Send [player name] is (leaving, returning). status must either
be "joined" or "left". """
        if status not in ("joined", "left"):
            raise ValueError("status must be \"joined\" or \"left\"")
        self.SendToAll({"action": "playerstatus",
                        "name": name,
                        "status": status})

    def SendToAll(self, data):
        [p.Send(data) for p in self.players]

    def SendToName(self, name, data):
        for player in self.players:
            if player.name == name:
                player.Send(data)

    def Launch(self):
        while True:
            self.Pump()
            time.sleep(0.0001)


def main(host, port):
    s = BangBangServer(localaddr = (host, port))
    s.Launch()
