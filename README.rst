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

Use the ToDus API in your Python projects.

Install
-------

To install run::

  pip install todus

Quickstart
----------

This is an example of how you would use this library in your projects:

.. code-block:: python

  from todus.client import ToDusClient

  client = ToDusClient()
  phone_number = "5312345678"

  # this only needs to be done once:
  client.request_code(phone_number)  # request SMS to start a new session
  pin = input("Enter PIN:").strip()  # enter the PIN received in SMS
  password = client.validate_code(phone, pin)  # you must save your session password to avoid having to verify via SMS again.
  print(f"Save your password: {password}")

  # get a token needed to upload/download files:
  token = client.login(phone_number, password)

  # uploading a file:
  file_path = "/home/user/Pictures/photo.jpg"
  with open(file_path, "rb") as file:
      data = file.read()
  url = client.upload_file(token, data)
  print(f"Uploaded file to: {url}")

  # downloading a file:
  size = client.download_file(token, url, path="my-photo.jpg")
  print(f"Downloaded {size} Bytes")
