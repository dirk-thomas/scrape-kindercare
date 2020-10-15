#!/usr/bin/env python3

# Copyright 2020 Dirk Thomas
# Licensed under the Apache License, Version 2.0

"""
Search emails to find KinderCare notifications and download the images/videos.
"""  # noqa: D200

import datetime
import os.path
import pickle
import re
import sys

from google.auth.transport.requests import Request

from google_auth_oauthlib.flow import InstalledAppFlow

from googleapiclient.discovery import build

from lxml import html

import requests

import yaml

MEDIA_DESTINATION = 'media'

# if modifying these scopes, delete the file gmail-token.pickle
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def main():  # noqa: D103
    # connect to GMail API
    creds = get_gmail_credentials()
    service = build('gmail', 'v1', credentials=creds)

    # login to KinderCare
    child_name, kindercare_username, kindercare_password = \
        get_kindercare_info()
    session = login_kindercare(kindercare_username, kindercare_password)

    # search for emails from KinderCare
    # optionally append ' before:YYYY/MM/DD' to the query to get older media
    message_ids = get_all_message_ids(
        service, 'from:no-reply@classroommail.kindercare.com')

    # read history to ignore previously considered emails
    if os.path.exists('previously-handled.yaml'):
        with open('previously-handled.yaml', 'rb') as h:
            handled_message_ids = yaml.safe_load(h)
    else:
        handled_message_ids = []

    for message_id in message_ids:
        id_ = message_id.get('id')

        # skip previously considered emails
        if id_ in handled_message_ids:
            print('.', end='')
            sys.stdout.flush()
            continue

        # get email metadata including the subject
        message = service.users().messages().get(
            userId='me', id=id_, format='metadata').execute()
        headers = message.get('payload').get('headers')
        subject = [
            h.get('value') for h in headers if h.get('name') == 'Subject'][0]

        # check if the subject refers to an image/video
        media_info = get_media_info(subject, child_name)
        if not media_info:
            print('.', end='')
        else:
            media_id, media_type = media_info

            # get timestamp of email to use for filename of media
            date_str = [
                h.get('value') for h in headers if h.get('name') == 'Date'][0]
            datetime_utc = datetime.datetime.strptime(
                date_str, '%a, %d %b %Y %X +0000 (UTC)')
            datetime_local = datetime_utc.replace(
                tzinfo=datetime.timezone.utc).astimezone(tz=None)
            datetime_local_str = datetime_local.strftime('%Y-%m-%d_%H-%M-%S')

            # fetch the media file
            media_url = 'https://classroom.kindercare.com/activities/' \
                f'{media_id}.{media_type}'
            response = session.get(media_url)
            try:
                assert response.ok
            except AssertionError:
                print()
                print(f'Failed to fetch: {media_url}', file=sys.stderr)
                continue
            assert response.status_code == 200

            # extract filename
            assert 'Content-Disposition' in response.headers
            content_disposition = response.headers['Content-Disposition']
            prefix = 'attachment; filename="'
            suffix = '"'
            assert content_disposition.startswith(prefix)
            assert content_disposition.endswith(suffix)
            filename = content_disposition[len(prefix):-len(suffix)]
            if filename.endswith('.MOV'):
                filename = filename[:-4] + '.mov'

            # write media file
            os.makedirs(MEDIA_DESTINATION, exist_ok=True)
            destination = os.path.join(
                MEDIA_DESTINATION,
                datetime_local_str + os.path.splitext(filename)[-1])
            assert not os.path.exists(destination)
            with open(destination, 'wb') as f:
                f.write(response.content)
            timestamp = datetime_local.timestamp()
            os.utime(destination, times=(timestamp, timestamp))
            print('+', end='')
        sys.stdout.flush()

        # persist updated list of considered emails
        handled_message_ids.append(id_)
        with open('previously-handled.yaml', 'w') as h:
            h.write(yaml.safe_dump(handled_message_ids))
    print()


def get_gmail_credentials():  # noqa: D103
    creds = None
    # the file gmail-token.pickle stores the user's access and refresh tokens,
    # and is created automatically when the authorization flow completes for
    # the first time
    if os.path.exists('gmail-token.pickle'):
        with open('gmail-token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # if there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'gmail-api.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # save the credentials for the next run
        with open('gmail-token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds


def get_kindercare_info():  # noqa: D103
    with open('kindercare.yaml', 'rb') as h:
        data = yaml.safe_load(h.read())
    return data['child_name'], data['username'], data['password']


def login_kindercare(username, password):  # noqa: D103
    # create session for subsequent requests
    session = requests.session()

    # get authenticity token
    login_url = 'https://classroom.kindercare.com/login'
    response = session.get(login_url)
    tree = html.fromstring(response.text)
    input_fields = tree.xpath("//input[@name='authenticity_token']/@value")
    assert len(input_fields) == 1
    authenticity_token = input_fields[0]

    # perform login
    response = session.post(
        login_url, data={
            'user[login]': username,
            'user[password]': password,
            'authenticity_token': authenticity_token,
        }, headers={'referer': login_url})
    assert response.ok
    assert response.status_code == 200
    return session


def get_all_message_ids(service, query):  # noqa: D103
    all_messages = []
    next_page_token = None
    # get each page of messages
    while True:
        messages, next_page_token = get_message_ids(
            service, query, next_page_token)
        print('.', end='')
        sys.stdout.flush()
        all_messages += messages
        if next_page_token is None:
            break
    print('', len(all_messages), 'message ids')
    return all_messages


def get_message_ids(service, query, page_token):  # noqa: D103
    results = service.users().messages().list(
        userId='me', q=query, pageToken=page_token).execute()
    return results.get('messages', []), results.get('nextPageToken')


def get_media_info(subject, child_name):  # noqa: D103
    # check if an email refers to an image or video
    pattern = '^' + child_name + r': (\*VIDEO\*)?.+ \[(\d+)\]$'
    match = re.match(pattern, subject)
    return (match.group(2), 'video' if match.group(1) else 'image') \
        if match else None


if __name__ == '__main__':
    main()
