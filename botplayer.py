class playerstatus(object):
    UNSTARTED = -1
    ENDED = 0
    PLAYING = 1
    PAUSED = 2
    BUFFERING = 3
    
    @staticmethod
    def getString(status):
        if status == playerstatus.UNSTARTED:
            return "unstarted"
        elif status == playerstatus.ENDED:
            return "ended"
        elif status == playerstatus.PLAYING:
            return "playing"
        elif status == playerstatus.PAUSED:
            return "paused"
        elif status == playerstatus.BUFFERING:
            return "buffering"
        else:
            return "unknown"
    

class pTrack(object):
    def __init__(self, player, uniqueIdentifier):
        self.player = player
        
        #'url':url,
            
        #Song Information
        #'title':title,
        #'artist':artist,
        #'album':album,
        #'duration':duration,
        
        #Title start time
        #'time':time


"""
    Base class for all players.
"""
class basePlayer(object):
    def __init__(self):
        self._state = playerstatus.UNSTARTED
    
    """
    Load song in player
    """
    def load(self):
        self._state = playerstatus.ENDED
    
    """
    Load song informations
    """
    def loadInfo(self, uniqueName, args=None):
        raise NotSupportedError("Base class function not replaced.")
        """
        return {
            'player': self,
            'url': url,
            
            #Song Information
            'title': title,
            'artist': artist,
            'album': album,
            'duration': duration,
            
            #Title start time
            'time': time
        }
        """
    
    """
    Is the player ready to be used.
    If this is False, any other functions of this class could fail.
    """
    def available(self):
        return False
    
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
    
    def getVolume(self):
        return -1.0
    
    def setVolume(self, level):
        pass
    
    @classmethod
    def createSong(player, url, title, artist="", album="", duration=-1.0, time=0.0):
        if not player:
            raise ValueError("player not defined")
        if not player:
            raise ValueError("player not defined")

        return {
            'player':player,
            'url':url,
            
            #Song Information
            'title':title,
            'artist':artist,
            'album':album,
            'duration':duration,
            
            #Title start time
            'time':time
        }
    
    
