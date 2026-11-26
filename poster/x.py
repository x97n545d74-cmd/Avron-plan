import os, sys, json, time, hmac, hashlib, base64, secrets, urllib.parse as up, urllib.request as ur, urllib.error
q = lambda s: up.quote(str(s), safe='~')
def call(method, url, body=None):
    o = {'oauth_consumer_key': os.environ['X_API_KEY'], 'oauth_nonce': secrets.token_hex(16),
         'oauth_signature_method': 'HMAC-SHA1', 'oauth_timestamp': str(int(time.time())),
         'oauth_token': os.environ['X_ACCESS_TOKEN'], 'oauth_version': '1.0'}
    base_url, _, qs = url.partition('?')
    params = dict(o); params.update(dict(up.parse_qsl(qs)))
    ps = '&'.join(f'{q(k)}={q(v)}' for k, v in sorted(params.items()))
    base = '&'.join([method, q(base_url), q(ps)])
    key = q(os.environ['X_API_SECRET']) + '&' + q(os.environ['X_ACCESS_TOKEN_SECRET'])
    o['oauth_signature'] = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    h = {'Authorization': 'OAuth ' + ', '.join(f'{q(k)}="{q(v)}"' for k, v in sorted(o.items()))}
    data = None
    if body is not None:
        data = json.dumps(body).encode(); h['Content-Type'] = 'application/json'
    try:
        r = ur.urlopen(ur.Request(url, data=data, headers=h, method=method), timeout=30)
        return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
def upload(path):
    """v2 simple media upload (multipart). Returns media id string or None."""
    import uuid
    o = {'oauth_consumer_key': os.environ['X_API_KEY'], 'oauth_nonce': secrets.token_hex(16),
         'oauth_signature_method': 'HMAC-SHA1', 'oauth_timestamp': str(int(time.time())),
         'oauth_token': os.environ['X_ACCESS_TOKEN'], 'oauth_version': '1.0'}
    url = 'https://api.x.com/2/media/upload'
    ps = '&'.join(f'{q(k)}={q(v)}' for k, v in sorted(o.items()))
    base = '&'.join(['POST', q(url), q(ps)])
    key = q(os.environ['X_API_SECRET']) + '&' + q(os.environ['X_ACCESS_TOKEN_SECRET'])
    o['oauth_signature'] = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    b = uuid.uuid4().hex
    def field(n, v): return f'--{b}\r\nContent-Disposition: form-data; name="{n}"\r\n\r\n{v}\r\n'.encode()
    body = field('media_category', 'tweet_image') + field('media_type', 'image/png') + \
        f'--{b}\r\nContent-Disposition: form-data; name="media"; filename="card.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + open(path, 'rb').read() + f'\r\n--{b}--\r\n'.encode()
    h = {'Authorization': 'OAuth ' + ', '.join(f'{q(k)}="{q(v)}"' for k, v in sorted(o.items())), 'Content-Type': f'multipart/form-data; boundary={b}'}
    try:
        r = ur.urlopen(ur.Request(url, data=body, headers=h, method='POST'), timeout=60); st, txt = r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        st, txt = e.code, e.read().decode()
    if st in (200, 201):
        d = json.loads(txt); d = d.get('data', d)
        return str(d.get('id') or d.get('media_id_string') or d.get('media_id'))
    print('UPLOAD_FAIL', st, txt[:300], flush=True); return None
if __name__ == '__main__':
    if sys.argv[1] == 'me':
        print(*call('GET', 'https://api.x.com/2/users/me'))
    elif sys.argv[1] == 'post':
        print(*call('POST', 'https://api.x.com/2/tweets', {'text': sys.stdin.read()}))
