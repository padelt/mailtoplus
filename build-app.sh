#!/bin/sh
# Creating a MacOS Application usually uses the system Python interpreter.
# If you use a Homebrew version of Python, this will lead to problems
# running the application on other machines.
# So by "resetting" the path the resulting App will be based on the
# system interpreter.
export PATH=/usr/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/X11/bin:~/bin
python setup.py py2app --verbose
