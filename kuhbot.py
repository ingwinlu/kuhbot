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

    def __init__(self, jid, password, rooms, nick):
    
        sleekxmpp.ClientXMPP.__init__(self, jid, password)
        
        self.rooms = rooms
        self.nick = nick
        
        # The session_start event will be triggered when
        # the bot establishes its connection with the server
        # and the XML streams are ready for use. We want to
        # listen for this event so that we we can initialize
        # our roster.
        self.add_event_handler("session_start", self.start)

        # The groupchat_message event is triggered whenever a message
        # stanza is received from any chat room. If you also also
        # register a handler for the 'message' event, MUC messages
        # will be processed by both handlers.
        self.add_event_handler("groupchat_message", self.muc_message)

        # The groupchat_presence event is triggered whenever a
        # presence stanza is received from any chat room, including
        # any presences you send yourself. To limit event handling
        # to a single room, use the events muc::room@server::presence,
        # muc::room@server::got_online, or muc::room@server::got_offline.
        
        #self.add_event_handler("muc::%s::got_online" % self.room,
        #                       self.muc_online)


        # The message event is triggered whenever a message
        # stanza is received. Be aware that that includes
        # MUC messages and error messages.
        self.add_event_handler("message", self.message)

    def start(self, event):
        """
        Process the session_start event.

        Typical actions for the session_start event are
        requesting the roster and broadcasting an initial
        presence stanza.

        Arguments:
            event -- An empty dictionary. The session_start
                     event does not provide any additional
                     data.
        """
        self.send_presence()
        self.get_roster()
        
        for room in self.rooms:
            self.plugin['xep_0045'].joinMUC(room,
                                        self.nick,
                                        # If a room password is needed, use:
                                        # password=the_room_password,
                                        wait=True)
                                        
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
        
        
        
    def muc_message(self, msg):
        """
        Process incoming message stanzas from any chat room. Be aware
        that if you also have any handlers for the 'message' event,
        message stanzas may be processed by both handlers, so check
        the 'type' attribute when using a 'message' event handler.

        Whenever the bot's nickname is mentioned, respond to
        the message.

        IMPORTANT: Always check that a message is not from yourself,
                   otherwise you will create an infinite loop responding
                   to your own messages.

        This handler will reply to messages that mention
        the bot's nickname.

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
        Process incoming message stanzas. Be aware that this also
        includes MUC messages and error messages. It is usually
        a good idea to check the messages's type before processing
        or sending replies.

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

if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO,
                        format='%(levelname)-8s %(message)s')

    # Setup the KuhBot and register plugins. Note that while plugins may
    # have interdependencies, the order in which you register them does
    # not matter.
    jid="kuhbot@jabber.at"
    password="NLs3QjGjS99eWS7ZfXnMzvn4"
    rooms = {"fo_shizzle@conference.jabber.at"}
    nick="kuhbot"
    
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
        
