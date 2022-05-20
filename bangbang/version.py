"""
Read the version from version
"""

#print "Do print statements even work?"

# Try/except is needed for setup.py
try:
    reader = open("version", "r")
    #print "Tried \"version\""
except IOError:
    reader = open("bangbang/version", "r")
    #print "Didn't work, trying \"bangbang/version\""

__version__ = reader.read().strip()
reader.close()

del reader
