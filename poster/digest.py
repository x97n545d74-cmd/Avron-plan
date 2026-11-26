"""Hourly market digest for @AvronMoneytalks.

  python3 poster/digest.py poster collect            -> JSON of items since the last digest (no sources)
  python3 poster/digest.py poster post FILE [--dry]  -> post FILE as a thread, record it, push

FILE is JSON: {"parts": ["post 1", "post 2", ...], "covers_until": "YYYY-MM-DD HH:MM"}
The writing rules are in poster/DIGEST_RULES.md. Run only when run.py is not running.
"""
import json, sys, re, subprocess, datetime, zoneinfo, time
sys.path.insert(0, sys.argv[1]); import x
D = 'avron-x-merger/'; IST = zoneinfo.ZoneInfo('Asia/Kolkata')
def now(): return datetime.datetime.now(IST)
def git(*a):
    r = subprocess.run(['git', *a], capture_output=True, text=True)
    if r.returncode: raise SystemExit(f'git {a[0]} failed: {r.stderr.strip()}')
def load(f): return [json.loads(l) for l in open(D + f) if l.strip()]
def digest_id(t): return 'digest-' + t.strftime('%Y%m%d-%H')

git('pull', '--rebase', 'origin', 'avron-x-merger')
posted = load('posted.jsonl'); mode = sys.argv[2]
digests = [p for p in posted if p['id'].startswith('digest-')]
t = now()

if mode == 'collect':
    since = digests[-1]['covers_until'] if digests and digests[-1].get('covers_until') else (t - datetime.timedelta(minutes=65)).strftime('%Y-%m-%d %H:%M')
    q = load('queue.jsonl'); q += load('radar.jsonl')
    items = [{k: i.get(k) for k in ('id', 'created_ist', 'lane', 'company', 'headline', 'detail')} for i in q if i['created_ist'] >= since]
    print(json.dumps({'now_ist': t.strftime('%Y-%m-%d %H:%M'), 'this_hour_id': digest_id(t),
                      'already_posted_this_hour': any(d['id'] == digest_id(t) for d in digests),
                      'items_since': since, 'count': len(items), 'items': items}, indent=1, ensure_ascii=False))
    raise SystemExit

if mode == 'post':
    spec = json.load(open(sys.argv[3])); parts = spec['parts']; dry = '--dry' in sys.argv
    did = digest_id(t)
    problems = []
    if any(d['id'] == did for d in digests): problems.append(f'a digest for this hour ({did}) is already posted')
    if not 2 <= len(parts) <= 7: problems.append('use 2 to 7 parts')
    for n, p in enumerate(parts, 1):
        if len(p) > 280: problems.append(f'part {n} is {len(p)} characters (max 280)')
        if '#' in p: problems.append(f'part {n} has a hashtag')
        if re.search(r'https?://|www\.', p, re.I): problems.append(f'part {n} has a link (never post sources)')
    if problems:
        print('NOT POSTED:'); [print(' -', m) for m in problems]; raise SystemExit(1)
    if dry:
        print('DRY RUN OK'); [print(f'\n[{n}/{len(parts)}] ({len(p)} chars)\n{p}') for n, p in enumerate(parts, 1)]; raise SystemExit
    ids = []
    for n, p in enumerate(parts):
        body = {'text': p}
        if ids: body['reply'] = {'in_reply_to_tweet_id': ids[-1]}
        st, resp = x.call('POST', 'https://api.x.com/2/tweets', body)
        if st != 201:
            print('ERROR', f'part {n+1}/{len(parts)}', st, resp)
            if ids:  # record the partial thread so it is never posted twice
                posted.append({'id': did, 'posted_ist': t.strftime('%Y-%m-%d %H:%M'), 'tweet_id': ids[0], 'thread_tweet_ids': ids, 'kind': 'digest', 'partial': True, 'covers_until': spec.get('covers_until', '')})
                open(D + 'posted.jsonl', 'w').write(''.join(json.dumps(r) + '\n' for r in posted))
                git('add', D + 'posted.jsonl'); git('commit', '-m', f'Digest {did} partial'); git('pull', '--rebase', 'origin', 'avron-x-merger'); git('push', '-u', 'origin', 'avron-x-merger')
            raise SystemExit(1)
        ids.append(json.loads(resp)['data']['id']); time.sleep(2)
    posted.append({'id': did, 'posted_ist': t.strftime('%Y-%m-%d %H:%M'), 'tweet_id': ids[0], 'thread_tweet_ids': ids, 'kind': 'digest', 'covers_until': spec.get('covers_until', t.strftime('%Y-%m-%d %H:%M'))})
    open(D + 'posted.jsonl', 'w').write(''.join(json.dumps(r) + '\n' for r in posted))
    git('add', D + 'posted.jsonl')
    git('commit', '-m', f"Poster: hourly digest {did}\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01Ns1uU9PFXc9m84zBiLW7x1")
    git('pull', '--rebase', 'origin', 'avron-x-merger'); git('push', '-u', 'origin', 'avron-x-merger')
    print('OK', did, len(parts), 'parts', ids[0])
