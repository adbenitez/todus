ToDus client
============

.. image:: https://img.shields.io/pypi/v/todus.svg
   :target: https://pypi.org/project/todus

.. image:: https://img.shields.io/pypi/pyversions/todus.svg
   :target: https://pypi.org/project/todus

.. image:: https://pepy.tech/badge/todus
   :target: https://pepy.tech/project/todus

.. image:: https://img.shields.io/pypi/l/todus.svg
   :target: https://pypi.org/project/todus

.. image:: https://github.com/adbenitez/todus/actions/workflows/python-ci.yml/badge.svg
   :target: https://github.com/adbenitez/todus/actions/workflows/python-ci.yml

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black

ToDus client for the command line and API to use in your Python projects.

Install
-------

To install the latest stable version run::

  pip install -U todus

To install the latest stable version and enable the 7z multivolume feature for split uploads::

  pip install -U 'todus[7z]'

To test the unreleased version run::

  pip install todus git+https://github.com/adbenitez/todus

Usage
-----

::

   usage: todus [-h] [-n PHONE-NUMBER] [-v] {login,upload,download,token,accounts} ...

   ToDus Client

   positional arguments:
     {login,upload,download,token,accounts}
       login               authenticate in server
       upload              upload file
       download            download file
       token               get a token
       accounts            list accounts

   optional arguments:
     -h, --help            show this help message and exit
     -n PHONE-NUMBER, --number PHONE-NUMBER
                           account's phone number, if not given the default account will be used
     -v, --version         show program's version number and exit.


Developer Quickstart
--------------------

This is an example of how you would use this library in your projects:

.. code-block:: python

  from todus.client import ToDusClient2

  client = ToDusClient2(phone_number="5312345678")

  # this only needs to be done once:
  client.request_code()  # request SMS to start a new session
  pin = input("Enter PIN:").strip()  # enter the PIN received in SMS
  client.validate_code(pin)
  # you must save your session's password to avoid having to verify via SMS again.
  print(f"Save your password: {client.password}")

  # you need to login to upload/download files:
  client.login()

  # uploading a file:
  file_path = "/home/user/Pictures/photo.jpg"
  with open(file_path, "rb") as file:
      data = file.read()
  url = client.upload_file(data)
  print(f"Uploaded file to: {url}")

  # downloading a file:
  size = client.download_file(url, path="my-photo.jpg")
  print(f"Downloaded {size:,} Bytes")
