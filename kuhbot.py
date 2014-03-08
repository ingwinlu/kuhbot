#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import getpass
import logging
import urllib.request
import urllib.parse
import re
import requests
import json
import configparser
from bs4 import BeautifulSoup

import sleekxmpp

# Python versions before 3.0 do not use UTF-8 encoding
# by default. To ensure that Unicode is handled properly
# throughout SleekXMPP, we will set the default encoding
# ourselves to UTF-8.
if sys.version_info < (3, 0):
    reload(sys)
    sys.setdefaultencoding('utf8')
else:
    raw_input = input


class KuhBot(sleekxmpp.ClientXMPP):
    #urls
    mathtexurl = "http://chart.apis.google.com/chart?cht=tx&chf=bg,s,FFFFFFFF&chco=000000&chl="
    shortenerurl = "https://www.googleapis.com/urlshortener/v1/url"
    
    #re_strings
    re_latex = r'\$\$(.*?)\$\$'
    re_link = r'https?://[^\s<>"]+|www\.[^\s<>"]+'

    #init
    def __init__(self, jid, password, rooms, nick):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)
        
        self.rooms = rooms
        self.nick = nick

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
        if (msg['mucnick'] != self.nick): 
            urlfinds = re.findall(self.re_link,msg['body'])
            latexfinds = re.findall(self.re_latex,msg['body'])
            
            ##print("----------------\n%s\n------------------" % (len(urlfinds)))
            
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
                        message = "Title: " + self.grab_title(find)
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
                soup = BeautifulSoup(res)
                retstring = soup.title.string.strip()
                logging.info('grab_title: %s' % (retstring))
                return retstring
            
        except AttributeError:
            logging.info('grab_title: AttributeError')
        except: 
            print ("grab_title:", sys.exc_info()[0])
        return ""        

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)-8s %(message)s')
    
    #configparser
    config = configparser.ConfigParser()
    config_file = 'kuhbot_config.txt'
    config['LOGIN'] =   {   'jid' : '',
                            'password' : '',
                            'nick' : ''
                        }
    config['ROOMS'] =   {}
                        
    config.read(config_file)
    jid = config.get('LOGIN','jid')
    password = config.get('LOGIN','password')
    nick = config.get('LOGIN','nick')
    rooms = list(config['ROOMS'].keys())
    
    
 
 
    # Setup the KuhBot and register plugins. Note that while plugins may
    # have interdependencies, the order in which you register them does
    # not matter.
    xmpp = KuhBot(jid, password, rooms, nick)
    xmpp.register_plugin('xep_0030') # Service Discovery
    xmpp.register_plugin('xep_0004') # Data Forms
    xmpp.register_plugin('xep_0045') # Multi-User Chat
    xmpp.register_plugin('xep_0060') # PubSub
    xmpp.register_plugin('xep_0199') # XMPP Ping

    # If you are working with an OpenFire server, you may need
    # to adjust the SSL version used:
    # xmpp.ssl_version = ssl.PROTOCOL_SSLv3

    # If you want to verify the SSL certificates offered by a server:
    # xmpp.ca_certs = "path/to/ca/cert"

    # Connect to the XMPP server and start processing XMPP stanzas.
    if xmpp.connect():
        # If you do not have the dnspython library installed, you will need
        # to manually specify the name of the server if it does not match
        # the one in the JID. For example, to use Google Talk you would
        # need to use:
        #
        # if xmpp.connect(('talk.google.com', 5222)):
        #     ...
        xmpp.process(block=True)
        print("Done")
    else:
        print("Unable to connect.")
        
