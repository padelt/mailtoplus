# mailtoplus: The 'mailto:' scheme plus attachments and multiple mails

Whenever you encouter a URI on the web that starts with `mailto:`,
you expect to have your email client start once you click it.
The specification is in [RFC6068](http://tools.ietf.org/html/rfc6068).
Among the specification are some nice features:

* can specify zero or more `to` addresses
* can specify `cc` adresses
* can specify email subject and/or body content
* can specify additional [RFC2822](https://tools.ietf.org/html/rfc2822#section-2.2)
  header fields

Sounds great, but here are some deficiencies:

* Mail client support varies a lot. Support for additional headers seems
  to be non-existant.
* Although UTF8-encoded domain names and header field values are a
  main change compared to RFC2368, client support for percent-encoded
  UTF8 representations of unicode codepoints outside US-ASCII varies.
* No attachment support whatsoever in the spec. There are client
  implementations that allow attaching a local file, but not one that
  needs to be downloaded.

Obviously, `mailtoplus` wants to fix the deficiencies. The proposed
solution is based on a helper application per platform (Windows, MacOS, Linux etc.)
and per email client (Thunderbird, Mail.app, Outlook, Evolution, Gmail)
that is registered with the operating system to be triggered once a
link with an mailtoplus-URI is encountered. The registration process
is also platform-dependant.

So far, only one client exists - Mail.app unter MaxOS X.
Please help add support for many more!

## Client support

Platform             | Email client    | exists
-------------------- | --------------- | --------------------------
MacOS X              | Mail.app        | Yes, you are looking at it
Windows              | Outlook         | No
Linux/Windows/Mac    | Thunderbird     | No

### Apple Mail.app under MacOS X

Works as a packaged Python script that uses dynamically generated
AppleScript to control Mail.app.


#### Usage

The Mail.app client helper application `mailtoplus.app` has to be run
before it can be used. Just double-click the icon in Finder and wait
for a popup that says 'The mailtoplus-scheme should now be registered.'.
If you move the application later, remember to re-run it once.

Now you should be able to launch a new email compose window in Mail.app
by triggering a suitable link such as [this](mailtoplus:to=one@example.org).

Triggering the link can be done by pasting the link into the address bar
of your favorite Webbrowser and hitting the Enter key.

If the link contains an attachment, you will be asked for permission
first. You can also specify if this domain (or local path) should be
allowed for attachments in the future without asking. The decision is
stored in `~/.mailtoplus.conf`. The directory `~/.mailtoplus-temp/` is
used to temporarily store the downloaded files until Mail.app could
grab them.

If multiple emails are created, mailtoplus will show a popup with the
number of emails created after the work is done.

#### Building

The mail.app client helper `mailtoplus.app` is created using `setup.py`
with the help of [py2app](https://pypi.python.org/pypi/py2app/):

    pip install -r requirements.txt
    python setup.py py2app

If you are using a non-standard Python distribution (like Homebrew),
look at `build-app.sh`. It resets the path to only include "normal"
paths. You need to do this if there are problems running the standalone
application on other Macs.

### Thunderbird

Might be possible by using the
[Thunberbird command line syntax](http://kb.mozillazine.org/Command_line_arguments_%28Thunderbird%29).

### Microsoft Outlook

Should be possible to do using [COM](http://www.boddie.org.uk/python/COM.html)
automation. The details could be messy - after all there are libraries
to help with it like [Outlook Redemption](http://www.dimastr.com/redemption/home.htm).

# Specification

Everything following `mailtoplus:` is a list of URL-encoded parameters that
should look familiar to HTTP GET parameters.
Each parameter is a key/value-pair delimited by '='. Pairs are delimited
by '&'. Everything besides simple decimal numbers and ASCII alphanumeric
characters is URL-encoded. Text must be encoded as UTF-8.

Multiple emails can be chained. Each email must start with a `to` key.
Each `to` marks the start of a new email. Each `to` is expected to trigger
one pre-composed email in the client.

Attachments can be added to an email using the `attachment` key.
The format of the value is a three-tuple of form `method,source,attachmentname`
with commas in between.

* **method** can be `local` (get the file from the local filesystem) or
  `url` (the file is to be downloaded from the URL).
* **source** specifies the path or URL.
  In case of a URL, it can contain username and password as per
  [RFC 3986 section 3.2.1](http://tools.ietf.org/html/rfc3986#section-3.2.1).
  An implementation must accept HTTP/HTTPS downloads. Other methods are
  optional.
* **attachmentname** is the filename that appears in the email. 

To ensure forward compatibility, unknown keys should be silently ignored.
To ensure forward compatibility, per-attachment objects with unknown method
should be silently ignored.

## Examples

* An email with the subject line `Et voilà!`: <br>
  `mailtoplus:to=one@example.org&subject=Et%20voil%C3%A0%21` <br>
  Note the URL-encoded character 'à' (Unicode codepoint 00E0,
  UTF-8 encoding 0xC3A0).
* Two emails - one with subject, the other without: <br>
  `mailtoplus:to=one@example.org&subject=email1&to=two@example.org
* Email with attachment downloaded from a password-protected site
  that appears as `report1.pdf` in the email:<br>
  `mailtoplus:to=one@example.org&attachment=url,https%3A%2F%2Fuser%3Apassword%40example.org/somereport,report1.pdf`

For more examples, see `tests.py`.

To ensure forward compatibility, unknown names should be silently ignored.
To ensure forward compatibility, per-attachment objects with unknown method
should be silently ignored.
  
## Specification version history

Version, date   | Changes/notes
--------------- | ---------------------------------------------
v1, 2014-11-27  | Initial version.

# Security considerations

When a per-email object specifies attachments, implementations should ask
for explicit permission before downloading anything to prevent unintended
download of malware to the local device. Storing the decision based on the
URL domain name is advised.

If the number of `to` keys is unusually high, implementations should ask 
for explicit permission before opening many email client windows.
This is not implemented in the Mail.app helper yet.

# Todo

* Support more clients - obviously.
* Refactor `mailtoplus.py` to untangle the general parts (parser) from the
  email client specific parts.

# Contributors

* Philipp Adelt (@padelt)
* WANTED!