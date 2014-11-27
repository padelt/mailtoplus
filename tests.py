# encoding: utf-8

import unittest
import StringIO
import platform
from mailtoplus import Mailtoplus, WrongSchemeException, MalformedUriException, ConfigManager

class TestParser(unittest.TestCase):

    def setUp(self):
        self.mtp = Mailtoplus()

    def test_wrong_scheme(self):
        self.assertRaises(WrongSchemeException, self.mtp.parse_uri, "whatever:")

    def test_standard(self):
        res = self.mtp.parse_uri("mailtoplus:to=one%40example.org")
        self.assertEqual(res, [{
            'to': ['one@example.org'],
            }])

    def test_wrong_missing_to(self):
        self.assertRaises(MalformedUriException, self.mtp.parse_uri, "mailtoplus:one@example.org&subject=Et%20voil%C3%A0%21")

    def test_wrong_missing_address(self):
        self.assertRaises(MalformedUriException, self.mtp.parse_uri, "mailtoplus:subject=Et%20voil%C3%A0%21")

    def test_wrong_encoding(self):
        self.assertRaises(MalformedUriException, self.mtp.parse_uri, "mailtoplus:to=%FF%FF%FF")

    def test_single(self):
        res = self.mtp.parse_uri("mailtoplus:to=one@example.org&subject=Et%20voil%C3%A0%21")
        self.assertEqual(res, [{
            'to': ['one@example.org'],
            'subject': u'Et voilà!',
            }])

    def test_trailing_ampersand(self):
        res = self.mtp.parse_uri("mailtoplus:to=one@example.org&subject=Et%20voil%C3%A0%21&")
        self.assertEqual(res, [{
            'to': ['one@example.org'],
            'subject': u'Et voilà!',
            }])

    def test_body(self):
        res = self.mtp.parse_uri("mailtoplus:to=one@example.org&body=One%20line.%0D%0AAnother%20line.&subject=Et%20voil%C3%A0%21")
        self.assertEqual(res, [{
            'to': ['one@example.org'],
            'subject': u'Et voilà!',
            'body': 'One line.\r\nAnother line.',
            }])

    def test_double_to(self):
        res = self.mtp.parse_uri("mailtoplus:to=one@example.org,two@example.org&subject=Et%20voil%C3%A0%21")
        self.assertEqual(res, [{
            'to': ['one@example.org', 'two@example.org'],
            'subject': u'Et voilà!',
            }])

    def test_double_email(self):
        res = self.mtp.parse_uri("mailtoplus:to=one@example.org&subject=Et%20voil%C3%A0%21&to=two@example.org")
        self.assertEqual(res, [
            {
                'to': ['one@example.org'],
                'subject': u'Et voilà!',
            },
            {
                'to': ['two@example.org'],
            },
        ])

    def test_attachment_url(self):
        res = self.mtp.parse_uri("mailtoplus:to=one@example.org&attachment=url,https%3A%2F%2Fuser%3Apassword%40test.local/whatever.jpeg,attachmentname1.jpg&subject=Et%20voil%C3%A0%21")
        self.assertEqual(res, [{
            'to': ['one@example.org'],
            'subject': u'Et voilà!',
            'attachment': [
                {'method': 'url', 'source': 'https://user:password@test.local/whatever.jpeg', 'attachmentname': 'attachmentname1.jpg'},
            ],
        }])

    def test_attachment_local(self):
        res = self.mtp.parse_uri("mailtoplus:to=one@example.org&attachment=local,file%3A%2F%2F%2Fc:%2Fsomedir%2Fsomefile.txt,attachmentname1.txt&attachment=local,file%3A%2F%2F%2Fhome%2Fusername%2Fsomefile.txt,attachmentname2.txt")
        self.assertEqual(res, [{
            'to': ['one@example.org'],
            'attachment': [
                {'method': 'local', 'source': 'file:///c:/somedir/somefile.txt', 'attachmentname': 'attachmentname1.txt'},
                {'method': 'local', 'source': 'file:///home/username/somefile.txt', 'attachmentname': 'attachmentname2.txt'},
            ],
        }])

class TestConfiguration(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.config = ConfigManager()

    def test_empty_config(self):
        content = ""

        self.assertEqual(self.config.configuration, {
            'safe_regions': {},
            'options': {},
        })

        self.config.read_configuration(StringIO.StringIO(''))

        self.assertEqual(self.config.configuration, {
            'safe_regions': {},
            'options': {},
        })

    def test_read_safe_regions(self):
        content = u"""safe_regions:
    "local,file:///c:/somedir/somefile.txt":
        method: local
        source: "file:///c:/somedir/somefile.txt"
        action: forbidden
    "local,file:///home/username/somefile.txt":
        method: local
        source: "file:///home/username/somefile.txt"
        action: forbidden
    "url,https://user:password@test.local":
        method: url
        source: "https://user:password@test.local"
        action: allowed
"""

        self.config.read_configuration(StringIO.StringIO(""))

        self.assertEqual(self.config.configuration, {
            'safe_regions': {},
            'options': {},
        })

        self.config.read_configuration(StringIO.StringIO(content))

        self.assertEqual(self.config.configuration, {
            'safe_regions': {
                'local,file:///c:/somedir/somefile.txt': {
                    'method': 'local',
                    'source': 'file:///c:/somedir/somefile.txt',
                    'action': 'forbidden',
                },
                'local,file:///home/username/somefile.txt': {
                    'method': 'local',
                    'source': 'file:///home/username/somefile.txt',
                    'action': 'forbidden',
                },
                'url,https://user:password@test.local': {
                    'method': 'url',
                    'source': 'https://user:password@test.local',
                    'action': 'allowed',
                },
            },
            'options': {},
        })

    def test_read_options(self):
        content = u"""options:
    someoption: somevalue
    someoption2: somevalue2
safe_regions:
    "local,file:///c:/somedir/somefile.txt":
        method: local
        source: "file:///c:/somedir/somefile.txt"
        action: forbidden
"""

        self.config.read_configuration(StringIO.StringIO(""))

        self.assertEqual(self.config.configuration, {
            'safe_regions': {},
            'options': {},
        })

        self.config.read_configuration(StringIO.StringIO(content))

        self.assertEqual(self.config.configuration, {
            'options': {
                'someoption': 'somevalue',
                'someoption2': 'somevalue2',
            },
            'safe_regions': {
                'local,file:///c:/somedir/somefile.txt': {
                    'method': 'local',
                    'source': 'file:///c:/somedir/somefile.txt',
                    'action': 'forbidden',
                },
            },
        })

    def test_get_region(self):
        self.assertEqual(self.config.get_region('url', u"http://a:b@c.com:128/what?ever&there=is", test=True), "http://c.com:128")
        self.assertEqual(self.config.get_region('url', u"https://a:b@c.com:128/what?ever&there=is", test=True), "https://c.com:128")
        if platform.system() == 'Windows':
            self.assertEqual(self.config.get_region('local', u"file:///c:/somedir/somefile.txt", test=True), "file:///c:/somedir/")
            self.assertEqual(self.config.get_region('local', u"file:///c:/somedir/", test=True), "file:///c:/somedir/")
        if platform.system() == 'Darwin':
            self.assertEqual(self.config.get_region('local', u"file:///home/username/somefile.txt", test=True), "file:///home/username/")
            self.assertEqual(self.config.get_region('local', u"file:///home/username/", test=True), "file:///home/username/")
        self.assertRaises(MalformedUriException, self.config.get_region, "url", "//a:b@c.com:128/")
        self.assertRaises(MalformedUriException, self.config.get_region, "url", "https:///ccc/")
        
    def test_set_savety(self):
        self.config.clear()
        if platform.system() == 'Windows':
            self.config.set_safety("local", "file:///c:/allow/", "allowed", test=True)
            self.config.set_safety("local", "file:///c:/forbidden/", "forbidden", test=True)
            self.assertEqual(self.config.get_safety('local', 'file:///c:/allow/abc.txt', test=True), 'allowed')
            self.assertEqual(self.config.get_safety('local', 'file:///c:/forbidden/abc.txt', test=True), 'forbidden')
            self.assertEqual(self.config.get_safety('local', 'file:///c:/else/abc.txt', test=True), None)
        elif platform.system() == 'Darwin':
            self.config.set_safety("local", "file:///home/username/allow/", "allowed", test=True)
            self.config.set_safety("local", "file:///home/username/forbidden/", "forbidden", test=True)
            self.assertEqual(self.config.get_safety('local', 'file:///home/username/allow/abc.txt', test=True), 'allowed')
            self.assertEqual(self.config.get_safety('local', 'file:///home/username/forbidden/abc.txt', test=True), 'forbidden')
            self.assertEqual(self.config.get_safety('local', 'file:///home/username/else/abc.txt', test=True), None)
        else:
            raise Exception()
        self.config.set_safety("url", "http://a:b@c.com:128/what?ever&there=is", "allowed", test=True)
        self.config.set_safety("url", "http://a:b@xx.com:128/what?ever&there=is", "forbidden", test=True)
        self.assertEqual(self.config.get_safety('url', 'http://a:b@c.com:128/what?ever&there=is', test=True), 'allowed')
        self.assertEqual(self.config.get_safety('url', 'http://c.com:128', test=True), 'allowed')
        self.assertEqual(self.config.get_safety('url', 'https://c.com:128', test=True), None)
        self.assertEqual(self.config.get_safety('url', 'http://rr:qq@xx.com:128/something?else', test=True), 'forbidden')

    def test_read_modify_write_reread(self):
        self.config.clear()
        self.config.read_configuration(StringIO.StringIO("""
safe_regions:
    "url,https://test.local":
        method: url
        source: 'https://test.local'
        action: allowed
    "url,https://test.forbidden.local":
        method: url
        source: 'https://test.forbidden.local'
        action: forbidden
"""))
        self.config.set_safety("url", "http://a:b@xx.com:128/what?ever&there=is", "forbidden", test=True)
        self.assertEqual(self.config.get_safety('url', 'https://test.local', test=True), 'allowed')
        self.assertEqual(self.config.get_safety('url', 'https://test.forbidden.local', test=True), 'forbidden')
        self.assertEqual(self.config.get_safety('url', 'http://a:b@xx.com:128/what?ever&there=is', test=True), 'forbidden')
        temp = StringIO.StringIO()
        self.config.write_configuration(temp)
        temp.seek(0)
        c2 = ConfigManager()
        c2.read_configuration(temp)
        self.assertEqual(c2.get_safety('url', 'https://test.local', test=True), 'allowed')
        self.assertEqual(c2.get_safety('url', 'https://test.forbidden.local', test=True), 'forbidden')
        self.assertEqual(c2.get_safety('url', 'http://a:b@xx.com:128/what?ever&there=is', test=True), 'forbidden')

    def test_get_safety(self):
        self.config.read_configuration(StringIO.StringIO("""
safe_regions:
    "local,file:///home/username/":
        method: local
        source: "file:///home/username/"
        action: allowed
    "local,file:///file:///home/username/":
        method: local
        source: "file:///file:///home/username/"
        action: allowed
    "local,file:///etc/":
        method: local
        source: "file:///etc/"
        action: forbidden
    "local,file:///etc/a/":
        method: local
        source: "file:///etc/a/"
        action: allowed
    "local,file:///etc/b/":
        method: local
        source: "file:///etc/b/"
        action: allowed
    "local,file:///c:/a/":
        method: local
        source: "file:///c:/a/"
        action: allowed
    "local,file:///c:/b/":
        method: local
        source: "file:///c:/b/"
        action: allowed
    "local,file:///c:/c/":
        method: local
        source: "file:///c:/c/"
        action: forbidden
    "url,https://test.local":
        method: url
        source: 'https://test.local'
        action: allowed
    "url,https://test.forbidden.local":
        method: url
        source: 'https://test.forbidden.local'
        action: forbidden
"""))

        print repr(self.config.read_configuration)
        if platform.system() == 'Windows':
            self.assertEqual(self.config.get_safety('local', 'file:///c:/a/file.txt', test=True), 'allowed')
            self.assertEqual(self.config.get_safety('local', 'file:///c:/a/../file.txt', test=True), None)
            self.assertEqual(self.config.get_safety('local', 'file:///c:/a/../b/file.txt', test=True), 'allowed')
            self.assertEqual(self.config.get_safety('local', 'file:///c:/a/../b/', test=True), 'allowed')
            self.assertEqual(self.config.get_safety('local', 'file:///c:/a/../c/', test=True), 'forbidden')
            self.assertEqual(self.config.get_safety('local', 'file:///c:/a/../c//', test=True), 'forbidden')
        if platform.system() == 'Darwin':
            self.assertEqual(self.config.get_safety('local', 'file:///etc/a/../b/file.txt', test=True), 'allowed')
            self.assertEqual(self.config.get_safety('local', 'file:///etc/c/file.txt', test=True), None)
            self.assertEqual(self.config.get_safety('local', 'file:///etc/a/file.txt', test=True), 'allowed')
            self.assertEqual(self.config.get_safety('local', 'file:///etc/a/../file.txt', test=True), 'forbidden')
            self.assertEqual(self.config.get_safety('local', 'file:///etc/a/../b/file.txt', test=True), 'allowed')
            self.assertEqual(self.config.get_safety('local', 'file:///etc/c/file.txt', test=True), None)
        self.assertEqual(self.config.get_safety('url', 'https://user:password@test.forbidden.local'), 'forbidden')
        self.assertEqual(self.config.get_safety('url', 'https://test.forbidden.local/whatever'), 'forbidden')
if __name__ == '__main__':
    unittest.main()