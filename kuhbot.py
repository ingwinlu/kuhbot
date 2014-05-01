#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import getpass
import logging
import urllib.request ## TODO:  need rwrite to work with requests
import urllib.parse ##   TODO:  no need for double the inports
import re
import requests
import json
import configparser
import time
from bs4 import BeautifulSoup, SoupStrainer
import feedparser
import threading
import sleekxmpp

from pid import Pid
from future import Future


# Python versions before 3.0 do not use UTF-8 encoding
# by default. To ensure that Unicode is handled properly
# throughout SleekXMPP, we will set the default encoding
# ourselves to UTF-8.
if sys.version_info < (3, 0):
    reload(sys)
    sys.setdefaultencoding('utf8')
else:
    raw_input = input
    
#https://wiki.python.org/moin/RssLibraries
class rssPull():
    url_list = None
    last_id_list = None
    
    def __init__(self, urlArray, startupPull = False):
        self.url_list = urlArray
        self.last_id_list = []
        if(startupPull == False): #pulls feed to populate last_id_list to not spam at startup
            self.getNewItems()
    
    def pull(self):
        logging.debug('rss pull')
        future_calls = [Future(feedparser.parse,rss_url) for rss_url in self.url_list]
        feeds = [future_obj() for future_obj in future_calls]
        
        entries = []
        for feed in feeds:
            entries.extend( feed[ "items" ] )
            
        sorted_entries = sorted(entries, key=lambda entry: entry["date_parsed"])
        sorted_entries.reverse() # for most recent entries first
        return sorted_entries
        
    def getNewItems(self):
        logging.debug('getNewItems')
        new_entries = []
        new_ids = []
        item_list = self.pull()
        #logging.debug('length of item_list: ' + repr(len(item_list)))
        for item in item_list:
            logging.debug('examine id: ' + item['id'])
            if(item['id'] not in self.last_id_list):
                logging.debug(item['id'] + ' is not in last id list')
                new_ids.append(item['id'])
                new_entries.append(item)
        self.last_id_list = self.last_id_list + new_ids
        logging.debug('new_ids' + ','.join(new_ids))
        logging.debug('new last_id_list:' + ','.join(self.last_id_list))
        return new_entries
        
    
class ticker():   
    def __init__(self, maxTime, function, functionArgs = None):
        self.maxTime = maxTime
        self.function = function
        self.functionArgs = functionArgs
        self.curTime = 1
        
    def tick(self):
        if(self.curTime == self.maxTime):
            self.function(*self.functionArgs)
            self.curTime = 1
        else:
            self.curTime = self.curTime + 1
            
class TickerThread():
    tickerArray=[]
    
    def __init__(self):
        pass
        
    def add(self, ticker):
        self.tickerArray.append(ticker)
        
    def start(self):
        self.t = threading.Thread(target=self.worker)
        self.t.daemon = True
        self.t.start()
        logging.info('start worker')
        
    def worker(self):
        logging.debug('worker init')
        while True:
            for ticker in self.tickerArray:
                ticker.tick()
            time.sleep(1)

class KuhBot(sleekxmpp.ClientXMPP): 
    #ticker
    tickerThread = None
    #urls
    mathtexurl = "http://chart.apis.google.com/chart?cht=tx&chf=bg,s,FFFFFFFF&chco=000000&chl="
    shortenerurl = "https://www.googleapis.com/urlshortener/v1/url"
    
    #re_strings
    re_latex = r'\$\$(.*?)\$\$'
    re_link = r'https?://[^\s<>"]+|www\.[^\s<>"]+'

    #restrainer
    soupStrainer = None

    #init
    def __init__(self, jid, password, rooms, nick, soupStrainer=SoupStrainer('title')):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)
        self.soupStrainer=soupStrainer       
        self.rooms = rooms
        self.nick = nick
        
        #add async events
        self.tickerThread = TickerThread()
        
        #self.tickerThread.add(ticker(5,self.send_message,('winlu@jabber.at', 'test', 'chat')))
        #self.tickerThread.add(ticker(60, self.rss_send,('winlu@jabber.at',)))
        
        #add event handlers
        self.add_event_handler("session_start", self.start)
        self.add_event_handler("groupchat_message", self.muc_message)      
        #self.add_event_handler("muc::%s::got_online" % self.room,self.muc_online)
        self.add_event_handler("message", self.message)

    def start(self, event):
        self.send_presence()
        self.get_roster()
        
        for room in self.rooms:
            self.plugin['xep_0045'].joinMUC(room,
                                        self.nick,
                                        # If a room password is needed, use:
                                        # password=the_room_password,
                                        wait=True)
        self.tickerThread.start()                                
        
    def run(self):
        logging.info('run')
        if xmpp.connect():
            xmpp.process(block=True)
            logging.info('closing')
        else:
            print("Unable to connect.")
            
    # events    
    def muc_message(self, msg):
        """
        Arguments:
            msg -- The received message stanza. See the documentation
                   for stanza objects and the Message stanza to see
                   how it may be used.
                   
            self.nick in msg['body']:
            self.send_message(mto=msg['from'].bare,
                              mbody="I heard that, %s." % msg['mucnick'],
                              mtype='groupchat')
        """
        logging.debug(repr(msg))
        logging.debug(repr(msg['mucnick']))
        logging.debug(repr(msg['mucroom']))
        logging.debug(repr(msg['from']))
        if (msg['mucroom'] == msg['from']):
            logging.debug('channelmessage discovered')
            
        elif (msg['mucnick'] != self.nick): 
            urlfinds = re.findall(self.re_link,msg['body'])
            latexfinds = re.findall(self.re_latex,msg['body'])
            
            if (len(latexfinds)>0):
                for find in latexfinds:
                    message = msg['mucnick'] + ": LaTeX <" + self.short_url(self.mathtextencode(find)) + ">"
                    self.send_message(mto=msg['from'].bare,
                              mbody=message,
                              mtype='groupchat')
                              
            if (len(urlfinds)>0):
                for find in urlfinds:
                    message = self.grab_title(find)
                    if message is not "":
                        message = "Title: " + message
                        self.send_message(mto=msg['from'].bare,
                                mbody=message,
                                mtype='groupchat')
        
            if (msg['body'].startswith("!latex")):
                message = msg['mucnick'] + ": LaTeX <" + self.short_url(self.mathtextencode(msg['body'][6:])) + ">"
                self.send_message(mto=msg['from'].bare,
                              mbody=message,
                              mtype='groupchat')
                              
            if (msg['body'].startswith("!shorten")):
                message = msg['mucnick'] + ": short_url <" + self.short_url(msg['body'][8:]) + ">"
                self.send_message(mto=msg['from'].bare,
                              mbody=message,
                              mtype='groupchat')
                


    def message(self, msg):
        """
        Arguments:
            msg -- The received message stanza. See the documentation
                   for stanza objects and the Message stanza to see
                   how it may be used.
        """
        if msg['type'] in ('chat', 'normal'):
            msg.reply("Thanks for sending\n%(body)s" % msg).send()

    def muc_online(self, presence):
        """
        Process a presence stanza from a chat room. In this case,
        presences from users that have just come online are
        handled by sending a welcome message that includes
        the user's nickname and role in the room.

        Arguments:
            presence -- The received presence stanza. See the
                        documentation for the Presence stanza
                        to see how else it may be used.
        
        if presence['muc']['nick'] != self.nick:
            self.send_message(mto=presence['from'].bare,
                              mbody="Hello, %s %s" % (presence['muc']['role'],
                                                      presence['muc']['nick']),
                              mtype='groupchat')
        """                    

        
    # helpers
    def mathtextencode(self, latex):
        """
        encode latex formula into url
        """
        
        logging.info('mathtextencode for %s' % (latex))
        return self.mathtexurl + urllib.parse.quote(latex)
        
    def short_url(self,url):
        logging.info('short_url for %s' % (url))
        headers = {'content-type': 'application/json'}
        payload = {"longUrl": url}
        url = self.shortenerurl
        r = requests.post(url,data=json.dumps(payload),headers=headers)
        logging.debug(r.json())
        logging.info(r.json()['id'])
        return r.json()['id']
        
    def grab_title(self,url):
        logging.info('grab_title: %s' % (url))
        try:
            res = urllib.request.urlopen(url)
            if(res.getheader("Content-Type").startswith("text/html")):
                logging.info('grab_title: %s' % ('html detected, extracting title'))
                soup = BeautifulSoup(res, parse_only=self.soupStrainer)
                retstring = soup.title.string.strip()
                logging.info('grab_title: %s' % (retstring))
                return retstring
            
        except AttributeError:
            logging.info('grab_title: AttributeError')
        except: 
            print ("grab_title:", sys.exc_info()[0])
        return "" 
        
    def rss_send(self, to):
        logging.info('rss_send')
        rss = rssPull(['http://rss.orf.at/news.xml', 'http://heroicdebugging.biz/feeds/all.atom.xml']) #should be constructed from configparser
        rss_items = rss.getNewItems()
        for item in rss_items:
            msg_string = 'Title: {0}\nLink: {1}'.format(item['title'],item['link'])
            self.send_message(mto=to, mbody=msg_string, mtype='chat')
        

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)-8s %(message)s')
    
    pidinstance = Pid('./.kuhbot_pid')
    if(pidinstance.read()==1):
        sys.exit(1)
    if(pidinstance.write()==1):
        sys.exit(1)
            
    #configparser
    try:
        config = configparser.ConfigParser()
        config_file = 'kuhbot_config.txt'
        config['LOGIN'] =   {   'jid'      : '',
                                'password' : '',
                                'nick'     : '',
                            }
        config['ROOMS'] =   {}
                            
        config.read_file(open(config_file))
        jid = config.get('LOGIN','jid')
        password = config.get('LOGIN','password')
        nick = config.get('LOGIN','nick')
        rooms = list(config['ROOMS'].keys())
    except FileNotFoundError as e:
        logging.error("I/O error: {0}".format(e))
        sys.exit(1)
    
    #setup Kuhbot
    xmpp = KuhBot(jid, password, rooms, nick)
    #xmpp = KuhBot(jid, password, [], nick)
    xmpp.register_plugin('xep_0030') # Service Discovery
    xmpp.register_plugin('xep_0004') # Data Forms
    xmpp.register_plugin('xep_0045') # Multi-User Chat
    xmpp.register_plugin('xep_0060') # PubSub
    xmpp.register_plugin('xep_0199') # XMPP Ping

    xmpp.run()
        
    pidinstance.release()
