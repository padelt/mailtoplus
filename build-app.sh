#!/bin/bash
# Creating a MacOS Application usually uses the system Python interpreter.
# If you use a Homebrew version of Python, this will lead to problems
# running the application on other machines.
# So we bundle the running python framework
python setup.py py2app --verbose --frameworks $(which python)
