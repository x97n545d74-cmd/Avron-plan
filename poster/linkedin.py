"""AVRON LinkedIn company-page poster.

Picks the high-value items (stories, brokerage targets, investor deals, Radar
market-close card) from queue.jsonl / radar.jsonl, posts each as ONE LinkedIn
post (story_text when present) plus a comment/follow sign-off, and records
progress in avron-x-merger/linkedin_posted.jsonl.

Limits: max 6 posts per IST day, max 1 per run, at least 60 min apart.
Never posts verify_link. The token is injected by the session proxy for
api.linkedin.com, so a dummy bearer is sent here.

Usage: python3 linkedin.py [--dry-run]   (run from the repo root)
"""
import json, os, re, sys, subprocess, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

D = 'avron-x-merger/'
LOG = D + 'linkedin_posted.jsonl'
IST = timezone(timedelta(hours=5, minutes=30))
ORG = os.environ.get('LINKEDIN_ORG_ID', '').strip()
VERSION = os.environ.get('LINKEDIN_VERSION', '202609')
DRY = '--dry-run' in sys.argv
MAX_DAY, GAP_MIN = 6, 60

ASK = {
    'story': 'What would you have done differently in their place? Tell us in the comments.',
    'targets': 'Which of these calls do you agree with? Tell us in the comments.',
    'deals': 'Which of these moves surprises you most? Tell us in the comments.',
    'radar': 'How did your portfolio do today? Tell us in the comments.',
}
FOLLOW = 'Follow AVRON for Indian markets, explained every day.'


def load(p):
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def eligible(it):
    lane = it.get('lane')
    if lane in ('story', 'targets', 'deals'):
        return True
    return lane == 'radar' and 'RC' in it['id']  # market-close card only


def body(it):
    text = (it.get('story_text') or it['post_text']).strip()
    return f"{text}\n\n{ASK[it['lane']]}\n\n{FOLLOW}"


def little(s):  # LinkedIn "little text": escape reserved characters
    return re.sub(r'([\\|{}@\[\]()<>#*_~])', r'\\\1', s)


def post(text):
    req = urllib.request.Request(
        'https://api.linkedin.com/rest/posts', method='POST',
        data=json.dumps({
            'author': f'urn:li:organization:{ORG}',
            'commentary': little(text),
            'visibility': 'PUBLIC',
            'distribution': {'feedDistribution': 'MAIN_FEED',
                             'targetEntities': [], 'thirdPartyDistributionChannels': []},
            'lifecycleState': 'PUBLISHED', 'isReshareDisabledByAuthor': False,
        }).encode(),
        headers={'Authorization': 'Bearer proxy-injects-this',
                 'Content-Type': 'application/json',
                 'LinkedIn-Version': VERSION, 'X-Restli-Protocol-Version': '2.0.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.headers.get('x-restli-id') or r.headers.get('x-linkedin-id') or ''


def main():
    if not DRY:
        subprocess.run(['git', 'pull', '--rebase', '-q'], check=True)
    now = datetime.now(IST)
    today = now.strftime('%Y%m%d')
    done = load(LOG)
    done_ids = {d['id'] for d in done}
    items = [i for i in load(D + 'queue.jsonl') + load(D + 'radar.jsonl')
             if eligible(i) and i['id'][:8] == today and i['id'] not in done_ids]
    items.sort(key=lambda i: i['id'])
    todays = [d for d in done if d['id'][:8] == today]
    print(f'LINKEDIN today={len(todays)}/{MAX_DAY} waiting={len(items)}')
    if DRY:
        for it in items:
            print('-----', it['id'], it['lane'], len(body(it)), 'chars')
            print(body(it))
        return
    if not ORG:
        sys.exit('LINKEDIN_ORG_ID is not set')
    if not items or len(todays) >= MAX_DAY:
        return
    if todays:
        last = datetime.strptime(todays[-1]['posted_ist'], '%Y-%m-%d %H:%M').replace(tzinfo=IST)
        if now - last < timedelta(minutes=GAP_MIN):
            print('LINKEDIN waiting for the 60-minute gap')
            return
    it = items[0]
    try:
        urn = post(body(it))
    except urllib.error.HTTPError as e:
        sys.exit(f'LINKEDIN ERROR {e.code}: {e.read().decode()[:500]}')
    with open(LOG, 'a') as f:
        f.write(json.dumps({'id': it['id'], 'posted_ist': now.strftime('%Y-%m-%d %H:%M'),
                            'linkedin_urn': urn}) + '\n')
    print('LINKEDIN OK', it['id'], urn)
    subprocess.run(['git', 'add', LOG], check=True)
    subprocess.run(['git', 'commit', '-q', '-m', f'LinkedIn: posted {it["id"]}\n\n'
                    'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n'
                    'Claude-Session: https://claude.ai/code/session_01Ns1uU9PFXc9m84zBiLW7x1'],
                   check=True)
    subprocess.run(['git', 'pull', '--rebase', '-q'], check=True)
    subprocess.run(['git', 'push', '-q', 'origin', 'HEAD'], check=True)


main()
