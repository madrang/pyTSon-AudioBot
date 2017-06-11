from audiobot.botplayer import playerstatus, basePlayer
from audiobot.ffMozREPL import Mozrepl

"""
A tab in firefox with from an unsupported website.
"""
class mozPlayer(basePlayer):
    
    def __init__(self):
        self._state = playerstatus.UNSTARTED
    
    def load(self):
        self._state = playerstatus.PLAYING
    
    def available(self):
        return True
    
    def getState(self):
        return self._state
    
    def play(self, pause=False):
        pass
    
    def getCurrentTime(self):
        return -1.0
    
    def getDuration(self):
        return -1.0
        
    def currentlyPlaying(self):
        return None
    
    def seek(self, time):
        pass
    
    def getUrl(self, uniqueName, args=None):
        raise NotSupportedError("Base class function not replaced.")
    
    def getVolume(self):
        return -1.0
    
    def setVolume(self, level):
        pass
    
    @classmethod
    def createSong(player, songUniqueName, title, artist="", album="", duration=-1.0, time=0.0):
        song = createSong(player.getUrl(songId), title, artist, album, duration, time)
        song.update({
            'player':player,
            'id':songId
        })
        return song
    
    
