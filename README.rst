Scrape KinderCare for images / videos
=====================================

The Python script queries the GMail API for notification emails from
`KinderCare <https://classroom.kindercare.com/>`_.
If they refer to an image or video the media file is being downloaded from the
KinderCare website.

Prerequisites
-------------

* Python 3
* The Python packages:

  * ``google-api-python-client``
  * ``google-auth-httplib2``
  * ``google-auth-oauthlib``
  * ``lxml``
  * ``requests``
  * ``PyYAML``

Configuration
-------------

Configure the names of the children (as it appears in the subject line of the
notification emails from Kindercare) as well as the username and password for
the KinderCare app / website in the file ``kindercare.yaml``.
The file ``kindercare.sample.yaml`` contains the necessary structure.

On the first run the credentials for the GMail API are set up.
Follow the instructions in the browser and copy-n-paste the generated
credentials into the file ``gmail-api.json``.
The file ``gmail-api.sample.json`` contains the necessary structure.

Usage
-----

The script ``scrape-kindercare.py`` can be called repeatedly.
It only considers notification emails which haven't been checked during past
invocations.
To reset that history delete the file ``previously-handled.yaml``.

All media files will be downloaded into a subdirectory ``media/CHILD-NAME``.
For the filename as well as the last accessed and modified time the timestamp
of the email is being used.
