#!/usr/bin/env python
# encoding: utf-8
"""Takes a URL in mailtoplus format and parses it to open
one or more new e-mails in Mail.app on MacOS X.
Optionally, attachments can be downloaded from provided
locations via HTTP/HTTPS.
To control Mail.app, an AppleScript is launched.
"""
"""
   Copyright 2014-2018 Philipp Adelt

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

import base64
import logging
import os.path
import platform
import re
import shutil
import ssl
from subprocess import Popen, PIPE, call
import traceback
import sys
import tempfile
import time
import urllib2
import urlparse
import yaml

__author__ = "Philipp Adelt"
__copyright__ = "Copyright 2014-2018"
__credits__ = ["Philipp Adelt"]
__license__ = "Apache License 2.0"
__version__ = "2.3.0"
__date__ = "2018-04-103"
__maintainer__ = "Philipp Adelt"
__email__ = "autosort-github@philipp.adelt.net"
__status__ = "Release"

import Tkinter
import tkMessageBox

scheme = 'mailtoplus'

class WrongSchemeException(Exception):
    pass

class MalformedUriException(Exception):
    pass

class MalformedAttachmentException(Exception):
    pass

class FileNotFoundException(Exception):
    pass

class IllegalArgumentError(ValueError):
    pass

class MailClientAutomationException(Exception):
    pass

class DownloadException(Exception):
    pass

def fileurl2path(fileurl):
    return re.sub("^file://", "", fileurl)

def path2fileurl(path):
    return "file://{0}".format(path).replace("\\", "/")

def initial_logging():
    log = logging.getLogger(__name__)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    log.addHandler(ch)
    return log

logger = initial_logging()

class ConfigManager():
    def __init__(self):
        self.clear()
        self.tempdir = None
        self.tempfiles = []
        self.tempfile_counter = 0

    def clear(self):
        self.configuration = {
            'safe_regions': {},
            'options': {
                'ssl': 'secure',
            },
        }

    def load_configuration(self, fullfilename):
        with open(fullfilename, 'r') as f:
            self.read_configuration(f)

    def save_configuration(self, fullfilename):
        with open(fullfilename, 'w') as f:
            self.write_configuration(f)

    def default_location(self):
        return os.path.join(os.path.expanduser("~"), ".mailtoplus.conf")

    def read_configuration(self, filelike):
        self.clear()

        config = yaml.load(filelike.read())
        if not isinstance(config, dict):
            return

        regions = config.get('safe_regions', None)
        if regions and isinstance(regions, dict):
            for region in regions.values():
                if not isinstance(region, dict):
                    continue
                try:
                    valid = True
                    d = {}
                    for key in ('method', 'source', 'action'):
                        if not isinstance(region[key], basestring):
                            valid = False
                        d[key] = region[key]

                    if not d['action'] in ('allowed', 'forbidden'):
                        valid = False

                    if valid:
                        self.configuration['safe_regions'][u",".join([d['method'], d['source']])] = d
                except:
                    raise

        options = config.get('options', None)
        if options and isinstance(options, dict):
            for key, value in options.items():
                if isinstance(key, basestring) and isinstance(value, basestring):
                    self.configuration['options'][key] = value

    def setup_logging(self):
        """If the configuration contains the key 'logfile' in the options-dict,
        the python logging is setup to the filename assumed to be in the key.
        The optional parameter 'loglevel' in the options-dict can be DEBUG,
        INFO (default), WARNING, ERROR or CRITICAL.
        If no logfile is specified, this is a no-op.
        """
        logfile = self.configuration['options'].get('logfile', None)
        if logfile and isinstance(logfile, basestring):
            ch = logging.FileHandler(logfile)

            level = self.configuration['options'].get('loglevel', None)
            if not level:
                level = 'INFO'

            ch.setLevel({
                'DEBUG': logging.DEBUG,
                'INFO': logging.INFO,
                'WARNING': logging.WARNING,
                'ERROR': logging.ERROR,
                'CRITICAL': logging.CRITICAL,
                }.get(level, logging.INFO))
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)


    def write_configuration(self, filelike):
        filelike.write(yaml.dump(self.configuration))

    def get_region(self, method, source, test=False):
        """Gets the canonical region.
        For local files, that is the directory the file is in.
        For URLs, this is the access method (HTTP, HTTPS) and server name.
        """
        if method == 'local' and source.startswith("file://"):
            localpath = fileurl2path(source)
            if not os.path.isfile(localpath) and not test:
                raise FileNotFoundException()
            return path2fileurl(os.path.abspath(os.path.dirname(localpath)))+"/"
        elif method == 'url':
            pr = urlparse.urlparse(source)
            if pr.scheme.lower() not in ('http', 'https'):
                raise MalformedUriException("scheme '{0}' not allowed.".format(pr.scheme))
            if not pr.netloc:
                raise MalformedUriException("Empty net location not allowed.")
            netloc = re.sub(r"^.*@", "", pr[1]) # strip credentials
            region = "{0}://{1}".format(pr[0], netloc)
            return region
        else:
            raise MalformedUriException("Unknown method '{0}' or malformed source '{1}'.".format(method, source))


    def get_safety(self, method, source, test=False):
        """Determine if a decision about safety is stored in the current configuration.
        Returns 'allowed', 'forbidden' or None if no information is available.
        """
        region = self.get_region(method, source, test=test)
        return self.configuration['safe_regions'].get(u",".join([method, region]), {}).get('action', None)

    def set_safety(self, method, source, action, test=False):
        if not method in ('local', 'url') or not action in ('allowed', 'forbidden'):
            raise IllegalArgumentError()
        region = self.get_region(method, source, test=test)
        self.configuration['safe_regions'][u','.join([method, region])] = {
            'method': method,
            'source': region,
            'action': action,
        }

    def get_tempdir(self):
        if not self.tempdir:
            self.tempdir = os.path.join(os.path.expanduser("~"), ".mailtoplus-temp")
        return self.tempdir

    def get_tempfilename(self, filename):
        directory = None
        while not directory or os.path.exists(directory):
            self.tempfile_counter += 1
            directory = os.path.join(self.get_tempdir(), "att{}".format(self.tempfile_counter))

        os.makedirs(directory)
        tfilename = os.path.join(directory, filename)

        self.tempfiles.append(tfilename)
        return tfilename

    def cleanup_tempdir(self):
        for tfile in self.tempfiles:
            os.remove(tfile)
            os.rmdir(os.path.dirname(tfile))
        self.tempfiles = []

class Mailtoplus():
    def __init__(self):
        self.re_pair = re.compile(r"^([^&=]+)=([^&=]+)$")

    def __decode_addresses(self, addresses):
        return map(self.__decode, addresses.split(","))

    def __decode(self, text):
        unquoted = urllib2.unquote(text)
        try:
            return unquoted.decode("utf-8")
        except UnicodeDecodeError, e:
            raise MalformedUriException("The unquoting '%s' did not yield a valid UTF-8 encoded string." % text)

    def parse_uri(self, uri):
        emails = []
        if not uri:
            return emails

        if not uri.startswith('%s:' % scheme):
            raise WrongSchemeException("URI has to start with '%s:'" % scheme)

        rest = uri.split(":", 1)[1]

        email = None
        for element in rest.split("&"):
            if element == '': # tolerate a trailing ampersand
                continue
            pair = self.re_pair.match(element)
            if not pair:
                raise MalformedUriException("Format of URI data should be %s:a=b&c=d" % scheme)


            key, value = pair.groups()
            if key == 'to':
                # file away the current email entry
                if email:
                    emails.append(email)
                email = {
                    'to': self.__decode_addresses(value),
                }

            else:
                if not email:
                    raise MalformedUriException("Start each new email with 'to='!")

                if key in set(["cc", "bcc"]):
                    email[key] = self.__decode_addresses(value)

                elif key in set(["subject", "body"]):
                    email[key] = self.__decode(value)

                elif key == 'attachment':
                    try:
                        method, source, attachmentname = value.split(',', 2)
                        if method not in ('local', 'url'):
                            raise MalformedAttachmentException("Attachment '%s' specifies an unknown method." % value)
                        if not 'attachment' in email:
                            email['attachment'] = []
                        email['attachment'].append(
                            {'method': method, 'source': self.__decode(source), 'attachmentname': self.__decode(attachmentname)},
                        )
                    except ValueError, e:
                        raise MalformedAttachmentException("Attachment '%s' has not the expected form." % value)

                else:
                    raise MalformedUriException("Found unknown key '%s'" % key)

        if email:
            emails.append(email)
        
        return emails

class MailClientHandler():
    def __init__(self, config):
        self.config = config

    def get_unhandled_safety_issues(self, emails):
        unhandled = {}
        for email in emails:
            for attachment in email.get('attachment', []):
                s = self.config.get_safety(attachment['method'], attachment['source'])
                if not s:
                    unhandled[self.config.get_region(attachment['method'], attachment['source'])] = attachment
        return unhandled

    def generate_email(self, email):
        pass # override me

    def download_attachments(self, email):
        # Download non-local sources to temporary location.
        # Regardless of source, places 'localsource' in email['attachment'][]
        # with full path to local file ready for being attached.
        try:
            ssl_insecure = ('insecure' == self.config.configuration.get('options', {}).get('ssl', 'secure'))
            for att in email.get('attachment', []):
                if att['method'] == 'local':
                    att['localsource'] = att['source']
                elif att['method'] == 'url':
                    url = att['source']

                    # urllib2 does not recognize embedded authentication credentials,
                    # so we make that a proper Request header and cancel out the data
                    # from the URL.
                    pr = urlparse.urlparse(url)
                    pair = '{0}:{1}'.format(pr.username, pr.password)
                    if pr.username:
                        url = url.replace(pair+'@', '', 1)

                    req = urllib2.Request(url, None,
                        {
                            'User-Agent': 'mailtoplus/{}'.format(__version__),
                        })

                    if pr.username:
                        req.add_header('Authorization', 'Basic {}'.format(base64.b64encode(pair)))

                    try:
                        if ssl_insecure:
                            ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
                            r = urllib2.urlopen(req, context=ctx)
                        else:
                            r = urllib2.urlopen(req)

                        filename = self.config.get_tempfilename(att['attachmentname'])

                        with open(filename, 'w+b') as fp:
                            att['localsource'] = filename
                            shutil.copyfileobj(r, fp)
                    except urllib2.URLError, e:
                        if "CERTIFICATE_VERIFY_FAILED" in str(e.reason):
                            if ssl_insecure:
                                raise DownloadException("URLError: CERTIFICATE_VERFIY_FAILED despite ssl_insecure! {0} for URL {1}".format(e.reason, att['source']))
                            else:
                                disable = tkMessageBox.askquestion("Disable certificate validation?",
                                    "SSL certificate could not be verified. Permanently disable this check? "+
                                    "'Yes' will disable the check and allow attackers to read the requests.\n\n",
                                    icon='warning')
                                if disable == 'yes':
                                    if not 'options' in self.config.configuration:
                                        self.config.configuration['options'] = {}
                                    self.config.configuration['options']['ssl'] = 'insecure'
                                    self.config.save_configuration(self.config.default_location())
                                    ssl_insecure = True
                                popup("Since this request failed, you need to retry. Bye!")
                                sys.exit(1)

                        raise DownloadException("URLError: {0} for URL {1}".format(e.reason, att['source']))
                    except urllib2.HTTPError, e2:
                        raise DownloadException("HTTPError: " + e.message)
        except Exception, e:
            self.config.cleanup_tempdir()
            raise e


class MailAppHandler(MailClientHandler):

    def __generate_applescript(self, email):
        to = ['make new to recipient with properties {{address:"{}"}} at the end of to recipients'.format(
            a) for a  in email['to']]
        cc = ['make new cc recipient with properties {{address:"{}"}} at the end of to recipients'.format(
            a) for a  in email.get('cc', [])]
        bcc = ['make new bcc recipient with properties {{address:"{}"}} at the end of to recipients'.format(
            a) for a  in email.get('bcc', [])]
        atts = [u'make new attachment with properties {{file name:"{}"}}'.format(
            a['localsource']) for a in email.get('attachment', []) ]
        script = u"""
on run
    set theSignature to ""
    tell application "Mail"
        set _mailbox to my find_mailbox(mailboxes)
        if _mailbox = "" then
            my logit("no mailbox found")
        else
            my logit("found: " & (name of _mailbox))
        end if
        
        set _message to ""
        if _mailbox is not "" then
            my logit("mailtoplus folder: " & " " & (name of _mailbox) & (count of _mailbox's messages))
            if (count of _mailbox's messages) > 0 then
                set _message to item 1 in _mailbox's messages
                my logit("mailtoplus message: " & (subject of _message))
                my logit("mailtoplus body: " & (content of _message))
            end if
        end if
        -- make new message
        set newMail to make new outgoing message
        tell newMail
            set subject to "{subject}"
            if _message is not "" then
				set content to "{body}" & (content of _message)
			else
                set content to "{body}"& "

"
			end if

{to}
{cc}
{bcc}
            set visible to true
            -- set message signature of newMail to first signature of application "Mail"
{attachments}
        end tell
        activate
    end tell
end run
to logit(log_string)
	set log_file to "mailtoplus-as.log"
	do shell script "echo `date '+%Y-%m-%d %T: '`\\"" & log_string & "\\" >> $HOME/Library/Logs/" & log_file
end logit
to find_mailbox(_mailboxes)
	if (count of _mailboxes) = 0 then
		return ""
	end if
	
	repeat with _mailbox in _mailboxes
		logit("Looked at: " & (name of _mailbox))
		if (name of _mailbox) starts with "mailtoplus" then
			my logit("Returning: " & (name of _mailbox))
			return _mailbox
		end if
	end repeat
	return ""
	
end find_mailbox
""".format(
        to      = u'\n'.join(to),
        cc      = u'\n'.join(cc),
        bcc     = u'\n'.join(bcc),
        subject = email.get('subject', u''),
        body    = email.get('body', u''),
        attachments = u'\n'.join(atts),
        )
        return script

    def execute_applescript(self, script):
        p = Popen(['osascript', '-'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate(script.encode('utf-8'))
        return (p.returncode, stdout, stderr)

    def generate_email(self, email):
        script = self.__generate_applescript(email)
        rc, stdout, stderr = self.execute_applescript(script)
        if rc != 0:
            raise MailClientAutomationException("Automating Mail.app failed with returncode {0} "+
                "and output '{1}' and '{2}'. Script was: {3}".format(rc, repr(stdout), repr(stderr), repr(script)))

def popup(message):
    syslog_this(message)
    root = Tkinter.Tk()
    root.withdraw()
    tkMessageBox.showinfo(message, message)

def handle_emails_macos_mailapp(uri):
    mailtoplus = Mailtoplus()
    config = ConfigManager()
    try:
        config.load_configuration(config.default_location())
    except IOError:
        config.clear()
    config.setup_logging()

    try:
        emails = mailtoplus.parse_uri(uri)
    except Exception, e:
        msg = "Parser failed for %s, original exception: %s" % (repr(uri), str(e))
        logger.critical(msg)
        raise Exception(msg)
    mailapp = MailAppHandler(config)

    unhandled = mailapp.get_unhandled_safety_issues(emails)
    for issue, att in unhandled.items():
        allow_now = tkMessageBox.askquestion("Authorize file attachment",
            "The link wants to attach a file from '{0}'. Allow that?".format(issue),
            icon='warning')
        remember = tkMessageBox.askquestion("Remember that decision?",
            "Should this decision be stored for future links?",
            icon='warning')

        if remember == 'yes':
            config.set_safety(att['method'], att['source'], 'allowed' if allow_now == 'yes' else 'forbidden')
            config.save_configuration(config.default_location())

        if allow_now != 'yes':
            # Abort processing.
            return

    for email in emails:
        try:
            mailapp.download_attachments(email)
            mailapp.generate_email(email)
        except:
            logger.exception("Download or Generate failed.")
            popup("Exception: %s" % traceback.format_exc())
            raise

    time.sleep(10) # give Mail.app time to grab attachments

    if len(emails) > 1:
        popup('{0} emails created successfully!'.format(len(emails)))

    call(['logger', 'Mailtoplus finished {0} emails successfully. Version {1} {2} running with sys.argv: {3}'.format(
        len(emails), __version__, __date__, str(sys.argv)
        )])

    config.cleanup_tempdir()

def syslog_this(message):
    call(['logger', message])

if __name__ == '__main__':
    if len(sys.argv) == 1:
        if platform.system() == 'Darwin':
            # Calling the App on MacOS is the way to register the scheme.
            popup("The {0}-scheme should now be registered.\nVersion {1}   {2}".format(scheme, __version__, __date__))
        else:
            popup("Please call this script with a mailtoplus-URI as the parameter!")
    else:
        if platform.system() == 'Darwin':
            handle_emails_macos_mailapp(sys.argv[1])
        else:
            popup("Sorry, no support for anthing other than MacOS yet.")
