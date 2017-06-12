"""%(name)s V%(version)s - Play music and other various audio streams.
 
Private Chat Usage:
        %(cmdlist)s
 
URL should be a Youtube Video. (Other player support to be added later)
remix playlist will only be used after all ts3 content has played.
 
Public Chat Usage:                   [ cmd = lastsong, play, stop ]
        %(name)s cmd...              - Start the command with the bot name.
        %(name)s.cmd...              - Use a space, a dot or any of [ /, \\, |, - ]
 
Copyright (c) 2017, Marc-Andre Ferland.
License: GNU General Public License v3.0, see LICENSE for more details.
"""

from ts3plugin import ts3plugin
import ts3lib, ts3defines, ts3client, pytson
#from PythonQt.QtSql import QSqlDatabase
from PythonQt.QtCore import QTimer
from configparser import ConfigParser

from subprocess import Popen, PIPE, STDOUT
import sys
import os
import socket
import time
import traceback
import io
import re
import pickle
from timeit import default_timer

from audiobot.ts3Ext import logLevel, userperm, ts3Error, ts3SessionHost, plugincommand
from audiobot.bbcode import BBCode
from audiobot.botplayer import playerstatus, basePlayer

from audiobot.youtubeparser import YouTubeParser
from audiobot.ffMozREPL import Mozrepl
from audiobot.mozPlayer import mozPlayer
from audiobot.mozYoutube import mozYoutube

class audiobot(ts3plugin):
    name = "AudioBot"
    requestAutoload = False
    version = "0.0.44"
    apiVersion = 21
    author = "Marc-Andre \"Madrang\" Ferland"
    description = "Manage music channel"
    offersConfigure = False
    commandKeyword = "ab"
    infoTitle = "Bot Status: "
    #menuItems = [(ts3defines.PluginMenuType.PLUGIN_MENU_TYPE_CLIENT, 0, "My Menu Item", "icon.png")]
    menuItems = []
    hotkeys = []
    
    cfgpath = "audiobot.conf"
    
    logLvl = logLevel.STANDARD
    
    timerDelay = 1000
    #Set to zero to try to reconnect each self.timerDelay
    timerDelayWhileConnectionLost = 5000
    #If _onTimerEvent takes more time than timerWarningMaxDelay to execute, display a warning.
    timerWarningMaxDelay = 300
    
    registeredCommands = {}
    
    audioPlayerStatus = playerstatus.UNSTARTED
    sessionPklPath = "audiosession.pkl"
    audioSession = {
        'lastsong':{
            'url':"",
            'title':"",
            'artist':"",
            'album':"",
            'duration':0.0
        },
        'playlist':[],
        'ytmix':{
            'title':"",
            'url':""
        }
    }
    
    channelDescriptionBanner = "### Music Channel ###"
    
    def __init__(self):
        self.settings = ts3client.Config()
        self.cfg = ConfigParser()
        
        #set defaults
        self.cfg.add_section("general")
        self.cfg.set("general", "guiLogLvl", str(logLevel.STANDARD))
        self.cfg.set("general", "fileLogLvl", str(logLevel.STANDARD))
        self.cfg.add_section("channel")
        self.cfg.set("channel", "deny recording", "False")
        self.cfg.set("channel", "update description", "False")
        self.cfg.set("channel", "description banner", self.channelDescriptionBanner)
        
        self.cfg.add_section("MozRepl")
        self.cfg.set("MozRepl", "KeepConnected", "True")
        self.cfg.add_section("timer")
        self.cfg.set("timer", "delay", "1000")
        self.cfg.set("timer", "delayWhileConnectionLost", "5000")
        self.cfg.set("timer", "warningMaxDelay", "500")
        
        #Read from cfg.
        fullcfgpath = pytson.getConfigPath(self.cfgpath)
        if os.path.isfile(fullcfgpath):
            try:
                self.cfg.read(fullcfgpath)
            except Exception as err:
                self.printLogMessage("Error reading config file \"%s\"." % fullcfgpath, logLevel.ERROR);
                self.printLogMessage(repr(err), logLevel.ERROR);
        
        #Setup loggin.
        cfgGeneral = self.cfg["general"]
        self.guiLogLvl = cfgGeneral.getint("guiLogLvl", fallback=logLevel.STANDARD)
        self.fileLogLvl = cfgGeneral.getint("fileLogLvl", fallback=logLevel.STANDARD)
        
        #Hold user information
        #Need settings to work.
        self.ts3host = ts3SessionHost(self)
        
        #Channel settings.
        cfgChannel = self.cfg["channel"]
        self.channelDescriptionBanner = cfgChannel.get("description banner", fallback=self.channelDescriptionBanner)
        self.updatePlaylistChannelDescription = cfgChannel.getboolean("update description", fallback=False)
        self.channelDenyRecording = cfgChannel.getboolean("deny recording", fallback=False)
        
        #Restore session.
        fullpklpath = pytson.getConfigPath(self.sessionPklPath)
        if os.path.isfile(fullpklpath):
            try:
                with open(fullpklpath, 'rb') as pkl_file:
                    self.audioSession = pickle.load(pkl_file)
                    self.printLogMessage("Audio session restored.", logLevel.INFORMATIVE)
            except Exception as err:
                self.printLogMessage("Error restoring audio session \"%s\"." % fullpklpath, logLevel.ERROR);
                self.printLogMessage(repr(err), logLevel.ERROR);
        
        #Load Bot, Init MozRepl.
        try:
            #Use not to invert the provided bool as AutoConnect != KeepConnected.
            autoConnectMozRepl = not self.cfg.getboolean("MozRepl", "KeepConnected", fallback=True)
            self.mozRepl = Mozrepl(autoConnect=autoConnectMozRepl)
            if not self.mozRepl.autoConnected():
                self.printLogMessage("MozRepl.Telnet is set to stay connected.")
                self.mozRepl.connect()
                if self.mozRepl.isConnected():
                    self.printLogMessage("%s is Now connected to FireFox." % self.name)
                else:
                    #Error, can't connect to MoxRepl.
                    self.printLogMessage("MozRepl.Telnet could not connect to firefox.", logLevel.ERROR)
            
            #Init Timer to watch Firefox and post updates.
            cfgTimer = self.cfg["timer"]
            self.timerDelay = cfgTimer.getint("delay", fallback=1000)
            self.timerDelayWhileConnectionLost = cfgTimer.getint("delayWhileConnectionLost", fallback=5000)
            self.timerWarningMaxDelay = cfgTimer.getint("warningMaxDelay", fallback=500)
            self.onTickTimer = QTimer ()
            #self.onTickTimer.setSingleShot(True)
            self.onTickTimer.connect('timeout()', self._onTimerEvent)
            self.onTickTimer.start(int(self.timerDelay))
            self.loadCommands()
            self.printLogMessage("%s loaded." % self.name)
        except Exception as err:
            self.printLogMessage(repr(err));
            self.printLogMessage(traceback.format_exc())
    
    def stop(self):
        self.printLogMessage("killing %s..." % self.name)
        
        if self.onTickTimer.isActive():
            self.onTickTimer.stop()
        self.onTickTimer.disconnect('timeout()', self._onTimerEvent)
        
        if not self.mozRepl.autoConnected() and self.mozRepl.isConnected():
            self.mozRepl.disconnect()
            self.printLogMessage("MozRepl.Telnet connection closed.")
        
        with open(pytson.getConfigPath(self.cfgpath), "w") as f:
            self.cfg.write(f)
        
        with open(pytson.getConfigPath(self.sessionPklPath), "wb") as pkl_file:
            pickle.dump(self.audioSession, pkl_file)
            self.printLogMessage("Audio session saved.", logLevel.INFORMATIVE)
        
        del self.settings
        
        self.printLogMessage("%s killed." % self.name, logLevel.FATAL)
    
    def configure(self, qParentWidget):
        pass
    
    def menuCreated(self):
        pass
    
    def infoData(self, schid, aid, atype):
         if atype == 0:
             #error, ip = ts3.getServerVariableAsString(schid, ts3defines.VirtualServerPropertiesRare.VIRTUALSERVER_IP)
             #yield [ip]
             yield "Clicked on a Server. schid:%s id:%s" % (schid, aid)
         elif atype == 1:
             yield "Clicked on a Channel. schid:%s id:%s" % (schid, aid)
             selectedChannel = self.ts3host.getChannel(schid, aid)
             if self.ts3host.getServer(schid).me.channel == selectedChannel:
                yield "My Channel"
             yield selectedChannel.name
         elif atype == 2:
             yield "Clicked on a Client. schid:%s id:%s" % (schid, aid)
             selectedUser = self.ts3host.getUser(schid, aid)
             yield "User:%s Perm:%s" % (selectedUser.name, userperm.getString(selectedUser.perm))
         else:
             yield "ItemType \""+str(atype)+"\" unknown."
    
    def onUserLoggingMessageEvent(self, logMessage, logLevel, logChannel, logID, logTime, completeLogString):
        pass
    
    def printLogMessage(self, msg, level=logLevel.DEBUG):
        if level & self.guiLogLvl != 0:
            ts3lib.printMessageToCurrentTab(BBCode.color(msg, logLevel.getColor(level)))
        
        #ts3lib.logMessage(msg, logLevel.getTS3LogLevel(level), channel, logID)
        
        if level & self.fileLogLvl != 0:
            pass
    
    """Keyword Arguments:
        - name -- The name of the program (default: sys.argv[0])
        - cmd -- command to be executed
        - usage -- A usage message (default: auto-generated from arguments)
        - description -- A description of what the program does
        - epilog -- Text following the argument descriptions
        - prefix_chars -- Characters that prefix optional arguments
        - fromfile_prefix_chars -- Characters that prefix files containing additional arguments
        - argument_default -- The default value for all arguments
        - conflict_handler -- String indicating how to handle conflicts
        - add_help -- Add a -h/-help option
    """
    def addCommand(self, name, cmd,
                                arguments={},
                                permLevel=2,
                                usage=None,
                                description=None,
                                epilog=None,
                                prefix_chars='-',
                                fromfile_prefix_chars=None,
                                argument_default=None,
                                error_on_confilct=True,
                                add_help=True):
        botCmd = plugincommand.create(self, name, cmd,
                                                arguments=arguments,
                                                permLevel=permLevel,
                                                usage=usage,
                                                description=description,
                                                epilog=epilog,
                                                prefix_chars=prefix_chars,
                                                fromfile_prefix_chars=fromfile_prefix_chars,
                                                argument_default=argument_default,
                                                error_on_confilct=error_on_confilct,
                                                add_help=add_help)
        self.registeredCommands.update({name:botCmd})
        return botCmd
    
    def runShellCommand(self, schid, userID, command, silent=False):
        procEnv = os.environ.copy()
        procEnv["LD_LIBRARY_PATH"] = "/usr/lib"
        
        proc = Popen(command, bufsize=1, stdout=PIPE, stderr=STDOUT, close_fds=True, env=procEnv)
        for line in iter(proc.stdout.readline, b''):
            self.printLogMessage(line.decode(sys.stdout.encoding))
            if silent == False:
                self.replyTo (schid, userID, line.decode(sys.stdout.encoding))
        proc.stdout.close()
        return proc.wait()
    
    def addToPlayList(self, url, user=None, index=-1):
        newItem = {
            'url': url,
            'title': YouTubeParser.grab_title(url),
            'artist': "",
            'album': "",
            'duration': 0.0,
            #User that submitted the request.
            'user':user
        }
        
        if index == -1:
            self.audioSession['playlist'].append(newItem)
        elif index <= len(self.audioSession['playlist']):
            self.audioSession['playlist'].insert(index, newItem)
        else:
            raise ValueError("index is out of range.")
            
        self.ts3host.sendTextMsg("Item added to playlist: %s" % self.formatSong(newItem))
        self.onPlaylistModifiedEvent()
    
    def replyTo(self, schid, toID, msg):
        err = ts3lib.requestSendPrivateTextMsg(schid, msg, toID)
        if err != ts3defines.ERROR_ok:
            self.printLogMessage("Error replying to client: (%s, %s)" % (err, ts3lib.getErrorMessage(err)[1]), logLevel.ERROR)
    
    def msgChanel(self, schid, msg):
        (err, myid) = ts3lib.getClientID(schid)
        if err != ts3defines.ERROR_ok:
            self.printLogMessage("Error getting client id: (%s, %s)" % (err, ts3lib.getErrorMessage(err)[1]), logLevel.ERROR)
            return
        
        (err, cid) = ts3lib.getChannelOfClient(schid, myid)
        if err != ts3defines.ERROR_ok:
            self.printLogMessage("Error getting channel id: (%s, %s)" % (err, ts3lib.getErrorMessage(err)[1]), logLevel.ERROR)
            return
        
        err = ts3lib.requestSendChannelTextMsg(schid, msg, cid)
        if err != ts3defines.ERROR_ok:
            self.printLogMessage("Error sending txt message: (%s, %s)" % (err, ts3lib.getErrorMessage(err)[1]), logLevel.ERROR)
    
    def updateCurrentlyPlaying(self):
        reservedTabUrl = self.mozRepl.get_tab_url(tabID=0)
        updated = False
        
        if self.audioSession['lastsong']['url'] == reservedTabUrl:
            self.printLogMessage("updateCurrentlyPlaying but url did not change.")
            return updated
        
        if reservedTabUrl.startswith("https://www.youtube.com/") or reservedTabUrl.startswith("https://youtu.be/"):
            title = self.mozRepl.get_tab_elementById_html("eow-title", tabID=0)
            if title:
                title = YouTubeParser.textFromHTML(title)
            #Result could be empty if page is still loading.
            if title and title != self.audioSession['lastsong']['title']:
                #Youtube has a tendency to reeuse the same DOM in firefox and cause it to return values from the previous page.
                #Assume that if the video id is different we should get a different title.
                
                songInfo = {
                    #Browser page
                    'url':reservedTabUrl,
                    
                    #Song Information
                    'title':title,
                    'artist':"",
                    'album':"",
                    'duration':self.mozRepl.get_tab_movie_player_duration(tabID=0),
                    
                    #Title start time
                    'time':0
                }
                
                if title.count('-') == 1:
                    # Artist - Title
                    tprts = title.split('-')
                    if len(tprts) == 2:
                        songInfo['artist'] = tprts[0].strip()
                        songInfo['title'] = tprts[1].strip()
                
                self.audioSession['lastsong'].update(songInfo)
                updated = True
                self.printLogMessage("Updated Currently playing.")
                
            #Log the event if the page returned the same title.
            elif title: self.printLogMessage("Page returned the same song data, is Tab still loading???")
            
            ytPlaylist = self.mozRepl.get_tab_elementByClassName_html("playlist-title", tabID=0)
            ytPlaylist = YouTubeParser.textFromHTML(ytPlaylist)
            if ytPlaylist:
                oldTitle = self.audioSession['ytmix']['title']
                self.audioSession['ytmix']['title'] = ytPlaylist
                self.audioSession['ytmix']['url'] = reservedTabUrl
                self.printLogMessage("Updated current ytmix url.")
                if oldTitle != ytPlaylist:
                    #Only on title change.
                    self.updateChannelDescription()
        if not updated:
            self.printLogMessage("Song Data not found, is Tab still loading???")
        return updated
    
    def updateChannelDescription(self):
        if self.updatePlaylistChannelDescription:
            self.ts3host.logMsg("Generating channel description", logLevel.TRACE)
            desc = self.channelDescriptionBanner
            desc = self.formatPlaylist(msg=desc, maxLen=40)
            desc = self.formatMixTitle(msg=desc, maxLen=50)
            
            #Center text.
            desc = BBCode.center(desc)
            
            for srv in self.ts3host.servers:
                try:
                    srv.logMsg("Updating channel:\r\n%s" % desc, logLevel.INFORMATIVE)
                    srv.me.channel.description = desc
                    srv.me.channel.flushUpdates()
                except ts3Error as err:
                    srv.logMsg(str(err), logLevel.ERROR)
    
    def formatCurrentlyPlaying(self, msg=""):
        songInfo = msg
        
        title = self.audioSession['lastsong']['title']
        url = YouTubeParser.sanitizeUrl(self.audioSession['lastsong']['url'], fullUrl=True, allowPlaylist=False)
        artist = self.audioSession['lastsong']['artist']
        album = self.audioSession['lastsong']['album']
        duration = self.audioSession['lastsong']['duration']
        songInfo = "%s\r\n                                %s" % (songInfo, BBCode.url(title, url))
        if duration and duration > 3:
            drt = time.gmtime(duration)
            timeStr = ""
            if drt.tm_hour > 0:
                timeStr = time.strftime("%H:%M:%S", time.gmtime(duration))
            else:
                timeStr = time.strftime("%M:%S", time.gmtime(duration))
            songInfo = "%s (%s)" % (songInfo, timeStr)
        if album != "":
            songInfo = "%s\r\n                                          %s" % (songInfo, album)
        if artist != "":
            songInfo = "%s\r\n                                                    %s" % (songInfo, artist)
        
        return songInfo
    
    def formatPlaylist(self, msg="", maxLen=128):
        if not 'playlist' in self.audioSession or len(self.audioSession['playlist']) == 0:
            return "{m}\r\n    Empty playlist !\r\n        Use {a} or {n} to play something".format(m=msg, a=BBCode.color("add", '#0cba00'), n=BBCode.color("next", '#00a2db'))
        
        msg += "\r\n"
        for song in self.audioSession['playlist']:
            msg = msg + self.formatSong(song, maxLen)
        return msg
    
    def formatSong(self, song, maxLen=128):
        msg = ""
        if 'user' in song and song['user']:
            msg = "%s%s - " % (msg, BBCode.color(song['user'].name, userperm.getColor(song['user'].perm)))
        
        title = song['title'].strip()
        if title:
            if len(title) > maxLen:
                title = title[:maxLen-2] + "..."
            msg = "%s%s\r\n" % (msg, title)
        else:
            msg = "%s[Unknown]\r\n" % msg
        return msg
    
    def formatMixTitle(self, msg=None, maxLen=128):
        if not 'ytmix' in self.audioSession or not 'title' in self.audioSession['ytmix']:
            return msg
        
        mixtitle = self.audioSession['ytmix']['title']
        if mixtitle.strip():
            if len(mixtitle) > maxLen:
                mixtitle = mixtitle[:maxLen-2] + "..."
            if not msg:
                return mixtitle
            return "%s\r\n%s" % (msg, mixtitle)
        else: return msg
    
    def _onTimerEvent(self):
        startTime = default_timer()
        try:
            #Check if connection was lost.
            if not self.mozRepl.autoConnected() and not self.mozRepl.isConnected():
                self.audioPlayerStatus = playerstatus.UNSTARTED
                self.printLogMessage("Connection was lost with MozRepl...", logLevel.ERROR)
                if self.onTickTimer.interval < self.timerDelayWhileConnectionLost:
                    self.printLogMessage("Slowing tick timer until reconnection...")
                    self.onTickTimer.setInterval(self.timerDelayWhileConnectionLost)
                self.mozRepl.connect()
                if not self.mozRepl.isConnected():
                    return
                self.onTickTimer.setInterval(self.timerDelay)
                self.printLogMessage("Connection restored!")
            
            #Monitor Firefox.
            reservedTabUrl = self.mozRepl.get_tab_url(tabID=0)
            if reservedTabUrl == "about:blank":
                self.audioPlayerStatus = playerstatus.UNSTARTED
                return
                
            if self.mozRepl.isLoadingDocument():
                self.audioPlayerStatus = playerstatus.UNSTARTED
                self.printLogMessage("Firefox is loading...")
                return
                
            if not reservedTabUrl.startswith("https://www.youtube.com/") and not reservedTabUrl.startswith("https://youtu.be/"):
                self.audioPlayerStatus = playerstatus.UNSTARTED
                return
            
            if not self.mozRepl.tab_movie_player_available(tabID=0):
                self.audioPlayerStatus = playerstatus.UNSTARTED
                self.printLogMessage("Player unavailable...")
                return
               
            playerStatus = self.mozRepl.get_tab_movie_player_state(tabID=0)
            if playerStatus == playerstatus.UNSTARTED or playerStatus == playerstatus.BUFFERING:
                #unstarted or buffering
                self.audioPlayerStatus = playerStatus
                self.printLogMessage("Player loading...")
                return
            elif playerStatus == playerstatus.PAUSED:
                #paused
                self.audioPlayerStatus = playerStatus
                return
            elif playerStatus == playerstatus.PLAYING:
                #Video Playing
                self.audioPlayerStatus = playerStatus
                if len(self.audioSession['playlist']) >= 1:
                    #Videos waiting in the playlist...
                    if 'duration' in self.audioSession['lastsong']:
                        durationTime = self.audioSession['lastsong']['duration']
                        if durationTime and durationTime > 2.0:
                            currentTime = self.mozRepl.get_tab_movie_player_current_time(tabID=0)
                            if currentTime + 1.5 >= durationTime:
                                self.printLogMessage("Starting from playlist at \"%s\" / \"%s\"" % (currentTime, durationTime))
                                #TODO Dont discard song data
                                nextItem = self.audioSession['playlist'].pop(0)
                                nextUrl = nextItem['url']
                                self.onPlaylistModifiedEvent()
                                if reservedTabUrl == self.audioSession['ytmix']['url']:
                                    #If the url was from ytmix, update mix url to resume on the next item.
                                    nextMixUrl = self.mozRepl.get_tab_elementByClassName_href("ytp-next-button ytp-button", tabID=0)
                                    if nextMixUrl:
                                        self.audioSession['ytmix']['url'] = nextMixUrl
                                self.mozRepl.set_tab_url(nextUrl, tabID=0)
            elif playerStatus == playerstatus.ENDED:
                #Video ended
                self.audioPlayerStatus = playerStatus
                nextUrl = None
                if len(self.audioSession['playlist']) >= 1:
                    #TODO Dont discard song data
                    nextItem = self.audioSession['playlist'].pop(0)
                    nextUrl = nextItem['url']
                    self.onPlaylistModifiedEvent()
                else:
                    nextUrl = self.audioSession['ytmix']['url']
                if nextUrl:
                    self.mozRepl.set_tab_url(nextUrl, tabID=0)
                    return
            else:
                self.audioPlayerStatus = playerstatus.UNSTARTED
                self.printLogMessage("Unknown Player Status: %s" % playerStatus)
            
            if reservedTabUrl != self.audioSession['lastsong']['url']:
                #Tab loaded a new page with a player.
                self.printLogMessage("Url updated: %s" % reservedTabUrl)
                if self.updateCurrentlyPlaying():
                    self.ts3host.sendTextMsg(self.formatCurrentlyPlaying(msg="Currently playing!"))
            
            #Retriger timer.
            if self.onTickTimer.isSingleShot():
                #Lazy updating...
                #Calculate a longer delay for the next update.
                #NOTIMPLEMENTED, for now, just recall start with timerDelay.
                self.onTickTimer.start(int(self.timerDelay))
        except Exception as e:
            self.printLogMessage("onTimerEvent has died...\n\"%s\"" % (repr(e)), logLevel.ERROR)
            self.printLogMessage(traceback.format_exc(), logLevel.ERROR)
        finally:
            onEventTime = (default_timer() - startTime) * 1000
            if onEventTime > (self.timerWarningMaxDelay * 2.0):
                self.printLogMessage("Warning onTimerEvent execution time above threshold {t}ms > {trh}ms".format(trh=(self.timerWarningMaxDelay * 2.0), t=onEventTime), logLevel.WARNING)
            elif onEventTime > self.timerWarningMaxDelay:
                self.printLogMessage("Warning onTimerEvent execution time above threshold {t}ms > {trh}ms".format(trh=self.timerWarningMaxDelay, t=onEventTime), logLevel.NOTICE)
            
    
    def onConnectStatusChangeEvent(self, schid, status, errorNumber):
        if status == ts3defines.ConnectStatus.STATUS_CONNECTION_ESTABLISHED:
            srv = self.ts3host.getServer(schid)
            mynick = srv.me.name
            sp = re.split(r"\d", mynick)
            #Check if numbers where added at the end of the current nickname.
            if len(sp) > 1 and sp[0] != mynick and sp[1] == "":
                for cli in srv.users:
                        if cli.name == sp[0]:
                            #kick user with the same name, but without the numbers.
                            cli.kick("Client not responding")
                            #Restore name.
                            srv.me.name = sp[0]
                            srv.me.flushUpdates()
                            return
    
    def printWelcome(self, user):
        permLvl = user.perm
        self.printLogMessage("Joined channel: %s id %s perm %s" % (user.name, user.uid, userperm.getString(permLvl)), logLevel.NOTICE)
        if user.perm >= userperm.FRIEND:
            #Friends or above.
            user.channel.sendTextMsg("Welcome back %s, Ready to play music!" % BBCode.color(user.name, userperm.getColor(permLvl)))
            srvName = "%s/%s" % (user.server.name, user.channel.name)
            srvName = BBCode.color(srvName, "#28e0c1")
            user.sendTextMsg("Welcome to %s" % srvName)
            user.sendTextMsg("Send 'play YoutubeUrl' to play some music!")
            user.sendTextMsg("Send 'stop' for silence.")
        elif user.perm == userperm.BLOCKED:
            #Blocked
            user.channel.sendTextMsg("%s, This time try to Listen and enjoy..." % user.name)
        else:
            #Neutral.
            user.channel.sendTextMsg("Welcome %s, friends of %s will play music, Listen and enjoy!" % (user.name, user.server.me.name))
    
    def onClientMoveEvent(self, schid, clientID, oldChannelID, newChannelID, visibility, moveMessage):
        currentChannel = self.ts3host.getServer(schid).me.channel
        
        if newChannelID == currentChannel.channelID:
            user = self.ts3host.getUser(schid, clientID)
            self.printWelcome(user)
    
    def processUserCommand(self, user, command, public=False):
        tokens = command.split(' ')
        if len(tokens) == 0:
            return False
        
        #Find the command and run it.
        if tokens[0] in self.registeredCommands:
            cmd = self.registeredCommands[tokens[0]]
            if cmd.permissionlevel > user.perm:
                user.logMsg('User \"{0}\" was denied acces to \"{1}\"'.format(user.name, command), logLevel.INFORMATIVE)
                if public and user.perm >= 0:
                    self.msgChanel(user.schid, "%s, Not authorised..." % user.name)
                else:
                    user.sendTextMsg("Not authorised to run \"%s\"" % (command))
                return False
            cmd.run(user, tokens[1:], public=public)
            user.logMsg('User \"{0}\" uid: {1} executed \"{2}\"'.format(user.name, user.uid, command), logLevel.INFORMATIVE)
            return True
        else:
            user.logMsg('User \"{0}\" tried to run an unknown command \"{1}\"'.format(user.name, command), logLevel.INFORMATIVE)
            if public:
                self.msgChanel(user.schid, "%s, Invalid request..." % user.name)
            else:
                user.sendTextMsg("Invalid command \"%s\"" % (command))
            #Send the reminder in private for both public and private request.
            user.sendTextMsg("Type 'help' for more informations.")
            return False
        
    
    def processCommand(self, schid, command):
        return self.processUserCommand(self.ts3host.getServer(schid).me, command, public=False)
    
    def onTextMessageEvent(self, schid, targetMode, toID, fromID, fromName, fromUniqueIdentifier, message, ffIgnored):
        (err, myid) = ts3lib.getClientID(schid)
        if err != ts3defines.ERROR_ok:
            self.printLogMessage("Error getting current client ID: (%s, %s)" % (err, ts3lib.getErrorMessage(err)[1]), logLevel.ERROR)
            return
        
        if fromID == myid:
            #Try to avoid to reply to self generated messages.
            return
        
        publicRequest = False
        if toID == 0:
            #Check if public message is for AudioBot.
            if message.startswith(self.name) == True:
                if not fromName or not fromName.strip():
                    #Invalid sender name
                    self.printLogMessage("UserID \"%s\" has an invalid name." % fromUniqueIdentifier, logLevel.ERROR)
                    return
                div = message[len(self.name):len(self.name)+1]
                if div == " " or div == "-" or div == "." or div == "/" or div == "\\" or div == "|":
                    message = message[len(self.name)+1:]
                    toID = myid
                    publicRequest = True
                else:
                    self.msgChanel(schid, "%s, Are you talking to me?" % fromName)
                    return
        if toID == myid:
            #Message for AudioBot.
            user = self.ts3host.getUser(schid, fromID)
            user.logMsg("Message received from %s id %s perm %s" % (fromName, fromUniqueIdentifier, userperm.getString(user.perm)), logLevel.DEBUG)
            if not fromName or not fromName.strip():
                #Invalid sender name
                self.printLogMessage("UserID \"%s\" has an invalid name." % fromUniqueIdentifier, logLevel.ERROR)
                return
            
            if user.perm >= userperm.NEUTRAL:
                #Unknown, Friends or above.
                cmdExecuted = self.processUserCommand(user, message, public=publicRequest)
            else:
                #Banned user
                if publicRequest:
                    self.replyTo(schid, fromID, "%s, sorry, im not listening to banned users..." % fromName)
                else:
                    self.replyTo(schid, fromID, "Banned...")
                    err = ts3lib.clientChatClosed(schid, fromUniqueIdentifier, fromID)
                    if err != ts3defines.ERROR_ok:
                        user.logMsg("Error closing chat: (%s, %s)" % (err, ts3lib.getErrorMessage(err)[1]), logLevel.ERROR)
    
    def onPlaylistModifiedEvent(self):
        self.updateChannelDescription()
    
    def onPluginCommandEvent(self, schid, pluginName, pluginCommand):
        pass
    
    def onTalkStatusChangeEvent(self, schid, status, isReceivedWhisper, clientID):
        user = self.ts3host.getUser(schid, clientID)
        #self.printLogMessage("Talk status change: %s, Status: %s" % (user.name, status), logLevel.TRACE)
        #Kicks a client from its current channel to the default one.
        #err = ts3lib.requestMuteClients(serverConnectionHandlerID, clientIDArray)
        #err = ts3lib.requestClientKickFromChannel(schid, clientID, kickReason)
    
    def onClientChatComposingEvent(self, schid, clientID, clientUniqueIdentity):
        user = self.ts3host.getUser(schid, clientID)
        self.printLogMessage("Composing: %s id %s perm %s" % (user.name, user.uid, userperm.getString(user.perm)), logLevel.TRACE)
    
    def onClientChatClosedEvent(self, schid, clientID, clientUniqueIdentity):
        user = self.ts3host.getUser(schid, clientID)
        self.printLogMessage("Closed chat: %s id %s perm %s" % (user.name, user.uid, userperm.getString(user.perm)), logLevel.NOTICE)
    
    def onClientPokeEvent(self, schid, fromClientID, pokerName, pokerUID, message, ffIgnored):
        #Do not ignore.
        ignorePoke = 0
        try:
            user = self.ts3host.getUser(schid, fromClientID)
            
            #is it me?
            if user.clientID == user.server.me:
                return ignorePoke
            
            self.printLogMessage("Poke: %s: %s" % (user.name, message), logLevel.NOTICE)
            user.poke("%s? No!" % user.name)
            #self.lastpoker = user
            
            #Poke received, ignore.
            ignorePoke = 1
        except Exception as err:
            self.printLogMessage("onClientPokeEvent error: %s" % str(err))
            return ignorePoke
        return ignorePoke
        
    
    def onUpdateClientEvent(self, schid, clientID, invokerID, invokerName, invokerUniqueIdentifier):
        user = self.ts3host.getUser(schid, clientID)
        self.printLogMessage("{name}.onUpdateClientEvent: schid: {0} | user: {1} | invokerID: {2} | invokerName: {3} | invokerUniqueIdentifier: {4}".format(schid,user.name,invokerID,invokerName,invokerUniqueIdentifier,name=self.name))
        if not user.isInChannel():
            return
        if self.channelDenyRecording and user.isRecording:
            user.logMsg("User kicked from channel for recording: {n} uid: {u}".format(n=user.name, u=user.uid))
            user.kick("Recording is not allowed")
        
    
    def onServerGroupListEvent(self, schid, serverGroupID, name, atype, iconID, saveDB):
        #atype (int) - type of the servergroup (0=template, 1=regular, 2=serverquery)
        if not atype == 1:
            return
            
        #saveDB (int) - set to 1 if memberships are saved to the server's database, otherwise set to 0
        #This is called for each servergroup on the server requested with ts3lib.requestServerGroupList
        
        self.printLogMessage("{name}.onServerGroupListEvent: schid: {0} | serverGroupID: {1} | name: {2} | atype: {3} | iconID: {4} | saveDB: {5}".format(schid,serverGroupID,name,atype,iconID,saveDB,name=self.name), logLevel.TRACE)
        srv = self.ts3host.getServer(schid)
        srv.updateServerGroup(serverGroupID, name, iconID)
    
    def onServerGroupClientListEvent(self, schid, serverGroupID, clientDatabaseID, clientNameIdentifier, clientUniqueID):
        #This is called for each member of a servergroup requested with ts3lib.requestServerGroupClientList.
        self.printLogMessage("{name}.onServerGroupClientListEvent: schid: {0} | serverGroupID: {1} | name: {2} | clientUniqueID: {3} | clientDatabaseID: {4}".format(schid,serverGroupID,clientNameIdentifier,clientUniqueID,clientDatabaseID,name=self.name), logLevel.TRACE)
        
    
    def onServerGroupClientAddedEvent(self, serverConnectionHandlerID, clientID, clientName, clientUniqueIdentity, serverGroupID, invokerClientID, invokerName, invokerUniqueIdentity):
        #This is called whenever a client is added to a servergroup.
        pass
    
    def onServerGroupClientDeletedEvent(self, serverConnectionHandlerID, clientID, clientName, clientUniqueIdentity, serverGroupID, invokerClientID, invokerName, invokerUniqueIdentity):
        #This is called whenever a client was removed from a servergroup.
        pass
    
    def onChannelGroupListEvent(self, schid, channelGroupID, name, atype, iconID, saveDB):
        #atype (int) - defines if the channelgroup is a templategroup (value==0) or a regular one (value==1)
        if not atype == 1:
            return
            
        #saveDB (int) - set to 1 if memberships are saved to the server's database, otherwise set to 0
        #ts3lib.requestChannelGroupList(ts3lib.getCurrentServerConnectionHandlerID())
        
        self.printLogMessage("{name}.onChannelGroupListEvent: schid: {0} | channelGroupID: {1} | name: {2} | atype: {3} | iconID: {4} | saveDB: {5}".format(schid,channelGroupID,name,atype,iconID,saveDB,name=self.name), logLevel.TRACE)
        srv = self.ts3host.getServer(schid)
        srv.updateChannelGroup(channelGroupID, name, iconID)
    
    def onClientChannelGroupChangedEvent(self, schid, channelGroupID, channelID, clientID, invokerID, invokerName, invokerUniqueIdentifier):
        user = self.ts3host.getUser(schid, clientID)
        self.printLogMessage("{name}.onClientChannelGroupChangedEvent: schid: {0} | user: {1} | channel:{2} | channelGroup:{3} | invokerID: {4} | invokerName: {5} | invokerUniqueIdentifier: {6}".format(schid,user.name,channelID,channelGroupID,invokerID,invokerName,invokerUniqueIdentifier,name=self.name))
        #TODO Update channel group ???
    
    def onFileTransferStatusEvent(self, transferID, status, statusMessage, remotefileSize, schid):
        pass
    
    
    """
    onClientIDsEvent(self, serverConnectionHandlerID, uniqueClientIdentifier, clientID, clientName)
    This is called for each client matching a specific uid requested by ts3lib.requestClientIDs.
    
    onChannelClientPermListEvent(self, serverConnectionHandlerID, channelID, clientDatabaseID, permissionID, permissionValue, permissionNegated, permissionSkip)
    ts3lib.requestChannelClientPermList.
    
    onChannelGroupPermListEvent(self, serverConnectionHandlerID, channelGroupID, permissionID, permissionValue, permissionNegated, permissionSkip)
    ts3lib.requestChannelGroupPermList.
    
    onChannelPermListEvent(self, serverConnectionHandlerID, channelID, permissionID, permissionValue, permissionNegated, permissionSkip)
    This is called for each granted permission of a channel requested by ts3lib.requestChannelPermList.
    
    onClientPermListEvent(self, serverConnectionHandlerID, clientDatabaseID, permissionID, permissionValue, permissionNegated, permissionSkip)
    This is called for each granted permission to a specific client requested with ts3lib.requestClientPermList.
    
    onPermissionListEvent(self, serverConnectionHandlerID, permissionID, permissionName, permissionDescription)
    This is called for each permission on the server requested with ts3lib.requestPermissionList.
    
    onServerGroupPermListEvent(self, serverConnectionHandlerID, serverGroupID, permissionID, permissionValue, permissionNegated, permissionSkip)
    This is called for each granted permission of a servergroup requested with ts3lib.requestServerGroupPermList.
    """
    
    ####################################################################################################################################################
    ##                                                                 LOAD COMMANDS                                                                  ##
    ####################################################################################################################################################
    
    def loadCommands(self):
        self.addCommand("info", self.cmd_printBotInfo, permLevel=userperm.SERVERADMIN, description="Bot status information.", add_help=False)
        self.addCommand("help", self.cmd_printHelp, permLevel=userperm.NEUTRAL, add_help=False)
        
        self.addCommand("playlist", self.cmd_playlist, permLevel=userperm.NEUTRAL, description="Display the current playlist.", add_help=False)
        self.addCommand("nowplaying", self.cmd_nowplaying, permLevel=userperm.NEUTRAL, description="Display the information about the currently playing song.", add_help=False)
        self.addCommand("stop", self.cmd_stop, permLevel=userperm.FRIEND, description="Stop current playback")
        
        #Skip to a different time in the currenly playing song.
        #self.addCommand("seek", self.printHelp, permLevel=1)
        
        
        #self.addCommand("prev", self.printHelp, permLevel=1)
        
        
        cmdArgs=[
            (['url'], {
                'nargs': '?',
                'default': 'check_string_for_empty',
                'help': 'Optional Youtube Url to open, if omitted, resume playback'
            })
        ]
        self.addCommand("play",
            self.cmd_play,
            permLevel=userperm.FRIEND,
            arguments=cmdArgs,
            usage='%(prog)s [-h] url',
            description="Resume playback or play a Youtube Url",
            epilog="Be responsible, this command is monitored..."
        )
        self.addCommand("remix",
            self.cmd_remix,
            permLevel=userperm.SERVERADMIN,
            arguments=cmdArgs,
            usage='%(prog)s [-h] url',
            description="Generate a playlist with content based on the currently playing song",
            epilog="Be responsible, this command is monitored..."
        )
        
        cmdArgs=[
            (['url'], {
                'nargs': '?',
                'default': 'check_string_for_empty',
                'help': 'Optional Youtube Url to add to the playlist, if omitted, skip to the next item in the playlist.'
            })
        ]
        self.addCommand("next",
            self.cmd_next,
            permLevel=userperm.FRIEND,
            arguments=cmdArgs,
            usage='%(prog)s [-h] url',
            description="Skip to the next song or if an url is specified, add it to the playlist as the next item.",
            epilog="Be responsible, this command is monitored..."
        )
        
        cmdArgs=[
            (['url'], {
                'help': 'Youtube Url to add to the playlist.'
            })
        ]
        self.addCommand("add",
            self.cmd_add,
            permLevel=userperm.FRIEND,
            arguments=cmdArgs,
            description="Add a song to the playlist.",
        )
        
        cmdArgs=[
            (['level'], {
                'type':float,
                'nargs': '?',
                'default': '-1.0',
                'help': 'Optional sound level from 0 to 100, if ommited, print the current sound level.'
            })
        ]
        self.addCommand("vol",
            self.cmd_vol,
            permLevel=userperm.SERVERADMIN,
            arguments=cmdArgs,
            usage='%(prog)s [-h] level',
            description="Display the current sound level or if a value is specied set the current sound level.",
            epilog="Be responsible, this command is monitored..."
        )
        
        self.addCommand("forceChannelUpdate",
            self.cmd_forceChannelUpdate,
            permLevel=userperm.SERVERADMIN,
            description="Force a channel description update if there is an issue.",
            add_help=False
        )
    
    def cmd_printHelp(self, user, args=None, public=False):
        cmdList = ""
        for name, cmd in self.registeredCommands.items():
            if cmd.parser.description:
                #Dark Green
                color = '#007c10'
                if cmd.permissionlevel > user.perm:
                    #Not autorized
                    #Dark Red.
                    color = '#7c0000'
                cmdName = BBCode.color(name, color)
                cmdList = "%s\r\n%s        - %s" % (cmdList, cmdName, cmd.parser.description)
        cmdList = cmdList.strip()
        print(__doc__ % {'name': self.name, 'version': self.version, 'cmdlist': cmdList})
    
    def cmd_printBotInfo(self, user, args=None, public=False):
        print("Name: {name}, Version: {version}".format(name=self.name, version=self.version))
        print("Connected to firefox: %s" % self.mozRepl.isConnected())
        print("Keep connection: %s" % (not self.mozRepl.autoConnected()))
        print("OnTickTimer.Interval: {}ms".format(self.onTickTimer.interval))
        print("TickTimer Lazy updating: %s" % self.onTickTimer.isSingleShot())
        print("Deny recording: %s" % self.channelDenyRecording)
        print("Update channel description: %s" % self.updatePlaylistChannelDescription)
        
        color = 'green'
        if self.audioPlayerStatus == playerstatus.UNSTARTED:
            color = 'red'
        elif self.audioPlayerStatus == playerstatus.PAUSED:
            color = 'blue'
        elif self.audioPlayerStatus == playerstatus.BUFFERING:
            color = 'yellow'
        print("Player Status: %s" % BBCode.color(playerstatus.getString(self.audioPlayerStatus), color))
        
        if self.audioPlayerStatus > playerstatus.UNSTARTED:
            #If player if running.
            print("Volume: %s%%" % self.mozRepl.tab_movie_player_getVolume(tabID=0))
            
            currentTime = self.mozRepl.get_tab_movie_player_current_time(tabID=0)
            durationTime = self.mozRepl.get_tab_movie_player_duration(tabID=0)
            print("Time: \"%s\" / \"%s\"" % (currentTime, durationTime))

    
    def cmd_play(self, user, args=None, public=False):
        schid = user.schid
        userID = user.clientID
        videoUrl = None
        
        if args.url == 'check_string_for_empty':
            if self.audioPlayerStatus == 2:
                #Video is paused, resume it.
                user.logMsg("Trying to resume: %s" % self.mozRepl.tab_movie_player_play(play=True, tabID=0))
                return
            
            videoUrl = self.audioSession['lastsong']['url']
            if videoUrl:
                print ("Resuming [URL]%s[/URL]" % videoUrl)
            else:
                print ("Nothing to resume from, missing url argument...")
                return
        else:
            videoUrl = args.url
        
        #Fix link pasting in ts3....
        if videoUrl.startswith("[URL]"):
            videoUrl = videoUrl[len("[URL]"):0-(len("[/URL]"))]
        
        if not videoUrl.startswith("https://www.youtube.com/") and not videoUrl.startswith("https://youtu.be/"):
            print ("The provided Url is not a Youtube video, unsuported content \"%s\"" % videoUrl)
            return
        
        videoUrl = YouTubeParser.sanitizeUrl(videoUrl, fullUrl=True, allowPlaylist=True)
        
        user.sendTextMsg("Sending url...")
        self.mozRepl.set_tab_url(videoUrl, tabID=0)
        user.sendTextMsg("Received the url with success, your song \"should\" start playing now.")
        if public:
            self.msgChanel(schid, "%s, Request received." % user.name)
        else:
            self.msgChanel(schid, "Received [URL]%s[/URL] from %s" % (videoUrl, user.name))
        return
    
    def cmd_remix(self, user, args=None, public=False):
        schid = user.schid
        userID = user.clientID
        
        videoUrl = None
        
        if args.url == 'check_string_for_empty':
            videoUrl = self.audioSession['lastsong']['url']
            #TODO, open next video if currently playing.
            if videoUrl:
                print ("Looking at [URL]%s[/URL] for Mix Url" % videoUrl)
            else:
                print ("No song to remix, missing url argument...")
                return
        else:
            videoUrl = args.url
        
        #Fix link pasting in ts3....
        if videoUrl.startswith("[URL]") == True:
            videoUrl = videoUrl[len("[URL]"):0-(len("[/URL]"))]
        
        #Is from Youtube.
        if not videoUrl.startswith("https://www.youtube.com/") and not videoUrl.startswith("https://youtu.be/"):
            print ("The provided Url is not a Youtube video, unsuported content \"%s\"" % videoUrl)
            return
        
        #Clean the provided url.
        videoUrl = YouTubeParser.sanitizeUrl(videoUrl, fullUrl=True, allowPlaylist=True)
        
        #Get Mix url.
        mixUrl = YouTubeParser.grab_mix_playlist_id(videoUrl, fullUrl=True)
        if (mixUrl == None):
            print ("        No Mix Url found...")
            return
        else:
            print ("        Found Mix Url [URL]%s[/URL]" % mixUrl)
            videoUrl = mixUrl
        
        #If playing or buffering
        if self.audioPlayerStatus == playerstatus.PLAYING or self.audioPlayerStatus == playerstatus.BUFFERING:
            #Add to the playlist.
            self.addToPlayList(videoUrl, user=user)
            #reply ("        Found Mix Url [URL]%s[/URL]" % mixUrl)
            if public:
                self.msgChanel(schid, "%s, Request received." % user.name)
            else:
                self.msgChanel(schid, "Received [URL]%s[/URL] from %s" % (videoUrl, user.name))
        else:
            user.sendTextMsg("Sending url...")
            self.mozRepl.set_tab_url(videoUrl, tabID=0)
            user.sendTextMsg("Received the url with success, your song \"should\" start playing now.")
            if public:
                self.msgChanel(schid, "%s, Request received." % user.name)
            else:
                self.msgChanel(schid, "Received [URL]%s[/URL] from %s" % (videoUrl, user.name))
    
    def cmd_stop(self, user, args=None, public=False):
        if self.audioPlayerStatus == playerstatus.PLAYING:
            #Video is playing, pause it.
            self.mozRepl.tab_movie_player_play(play=False, tabID=0)
            self.ts3host.sendTextMsg("Stopped by %s" % user.name)
            return
        
        #Invalid status send firefox to a blank page.
        user.sendTextMsg("Stopping...")
        self.mozRepl.set_tab_url("about:blank", tabID=0)
        user.sendTextMsg("Received the request with success, sound broadcast will stop...")
        self.ts3host.sendTextMsg("Stopped by %s" % user.name)
    
    def cmd_nowplaying(self, user, args=None, public=False):
        print(self.formatCurrentlyPlaying(msg="Currently playing:"))
    
    def cmd_playlist(self, user, args=None, public=False):
        print(self.formatPlaylist(msg="Playlist:", maxLen=64))
        print(self.formatMixTitle(msg="YtMix:", maxLen=64))
    
    def cmd_next(self, user, args=None, public=False):
        schid = user.schid
        userID = user.clientID
        
        if args.url == 'check_string_for_empty':
            #Skip to next video.
            nextUrl = None
            if len(self.audioSession['playlist']) >= 1:
                #TODO Dont discard song data
                nextItem = self.audioSession['playlist'].pop(0)
                nextUrl = nextItem['url']
                self.onPlaylistModifiedEvent()
            else:
                nextUrl = self.mozRepl.get_tab_elementByClassName_href("ytp-next-button ytp-button", tabID=0)
            if nextUrl:
                print ("        Found next Url [URL]%s[/URL]" % nextUrl)
            else:
                print ("        No next Url found in the current page...")
                return
            user.sendTextMsg("Sending url...")
            self.mozRepl.set_tab_url(nextUrl, tabID=0)
            user.sendTextMsg("Received the url with success, your song \"should\" start playing now.")
            if public:
                self.msgChanel(schid, "%s, Request received." % user.name)
            else:
                self.msgChanel(schid, "Received [URL]%s[/URL] from %s" % (nextUrl, user.name))
            return
        else:
            videoUrl = args.url
        
        #Fix link pasting in ts3....
        if videoUrl.startswith("[URL]") == True:
            videoUrl = videoUrl[len("[URL]"):0-(len("[/URL]"))]
        
        #Is from Youtube.
        if not videoUrl.startswith("https://www.youtube.com/") and not videoUrl.startswith("https://youtu.be/"):
            print ("The provided Url is not a Youtube video, unsuported content \"%s\"" % videoUrl)
            return
        
        #Clean the provided url.
        videoUrl = YouTubeParser.sanitizeUrl(videoUrl, fullUrl=True, allowPlaylist=True, allowTime=True)
        
        self.addToPlayList(videoUrl, user=user, index=0)
        print ("Url added as the next item.")
        
    
    def cmd_add(self, user, args=None, public=False):
        videoUrl = args.url
        
        #Remove BBCode received from the ts3 chat.
        if videoUrl.startswith("[URL]") == True:
            videoUrl = videoUrl[len("[URL]"):0-(len("[/URL]"))]
        
        #Is from Youtube.
        if not videoUrl.startswith("https://www.youtube.com/") and not videoUrl.startswith("https://youtu.be/"):
            print ("The provided Url is not a Youtube video, unsuported content \"%s\"" % videoUrl)
            return
        
        #Clean the provided url.
        videoUrl = YouTubeParser.sanitizeUrl(videoUrl, fullUrl=True, allowPlaylist=True, allowTime=True)
        
        cpos = len(self.audioSession['playlist'])
        self.addToPlayList(videoUrl, user=user)
        if cpos == 0:
            print ("Url added as the next item.")
        else:
            print ("Url added at position %s." % (cpos + 1))
    
    def cmd_vol(self, user, args=None, public=False):
        if self.audioPlayerStatus == playerstatus.UNSTARTED:
            print("Player not started.")
            return
        if args.level == -1.0:
            msg = "Volume: %s%%" % self.mozRepl.tab_movie_player_getVolume(tabID=0)
            if public:
                self.ts3host.sendTextMsg(msg)
            else:
                user.sendTextMsg(msg)
            return
        
        if 0 > args.level or args.level > 100:
            raise ValueError("level should be in between 0 - 100")
        self.mozRepl.tab_movie_player_setVolume(args.level, tabID=0)
        if public:
            self.ts3host.sendTextMsg("%s changed the volume to %s%%" % (user.name, args.level))
        else:
            self.ts3host.sendTextMsg("%s changed the volume to %s%%" % (user.name, args.level))
            user.sendTextMsg("Volume changed to %s%%" % args.level)
    
    def cmd_ban(self, user, args=None, public=False):
        pass
        #ts3lib.banclient(serverConnectionHandlerID, clientID, timeInSeconds, banReason)
    
    def cmd_forceChannelUpdate(self, user, args=None, public=False):
        if not self.updatePlaylistChannelDescription:
            print("Channel updating is disabled.")
            return
        self.updateChannelDescription()
        print("Channel updated.")
    
