import json, sys, time, subprocess, datetime, zoneinfo, os, re
sys.path.insert(0, sys.argv[1]); import x
D = 'avron-x-merger/'; LIMIT = 5
def git(*a):
    r = subprocess.run(['git', *a], capture_output=True, text=True)
    if r.returncode: raise SystemExit(f'git {a[0]} failed: {r.stderr.strip()}')
git('pull', '--rebase', 'origin', 'avron-x-merger')
posted = [json.loads(l) for l in open(D + 'posted.jsonl') if l.strip()]
byid = {p['id']: p for p in posted}
queue = [json.loads(l) for l in open(D + 'queue.jsonl') if l.strip()]
import os
if os.path.exists(D + 'radar.jsonl'):  # user said 'yes radar' on 18 Nov
    queue += [json.loads(l) for l in open(D + 'radar.jsonl') if l.strip()]
def parts(it): return it.get('thread') or [it['post_text']]
def done(it):
    p = byid.get(it['id'])
    return 0 if not p else len(p.get('thread_tweet_ids') or [p['tweet_id']])
new = [i for i in queue if i['id'] not in byid]
unfinished = [i for i in reversed(queue) if i['id'] in byid and done(i) < len(parts(i))]
sent = 0
def save(msg):
    with open(D + 'posted.jsonl', 'w') as f:
        for p in posted: f.write(json.dumps(p) + '\n')
    git('add', D + 'posted.jsonl')
    git('commit', '-m', msg + "\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01Ns1uU9PFXc9m84zBiLW7x1")
    git('pull', '--rebase', 'origin', 'avron-x-merger')
    git('push', '-u', 'origin', 'avron-x-merger')
import card
CARD_LANES = {'filing', 'nse', 'news', 'radar'}; CARDS_PER_DAY = 6; CARDS_PER_RUN = 1; carded = 0
today = datetime.datetime.now(zoneinfo.ZoneInfo('Asia/Kolkata')).strftime('%Y-%m-%d')
cards_today = sum(1 for p in posted if p.get('image') and p.get('posted_ist', '').startswith(today))
def wants_card(it, n):
    return (n == 0 and len(parts(it)) == 1 and it.get('lane') in CARD_LANES and card.hero_of(it['headline'])
            and carded < CARDS_PER_RUN and cards_today + carded < CARDS_PER_DAY and os.path.exists('/tmp/avron_cards_on'))
HOLD = set()   # parts held back for the user's check
def last_id(p): return [t for t in (p.get('thread_tweet_ids') or [p['tweet_id']]) if t.isdigit()][-1]
for it in new + unfinished:
    ps = parts(it)
    if it['id'] not in byid and len(ps) > 1:
        # X rejects identical text: if this opener is already live, hang the rest under that thread
        twin = next((o for o in queue if o['id'] in byid and o['id'] != it['id'] and parts(o)[0] == ps[0]), None)
        if twin:
            anchor = last_id(byid[twin['id']])
            p = {'id': it['id'], 'posted_ist': '', 'tweet_id': anchor, 'thread_tweet_ids': [anchor], 'opener_duplicate_of': twin['id']}
            posted.append(p); byid[it['id']] = p
            print('NOTE', it['id'], 'opener already live in', twin['id'], '- replying under that thread', flush=True)
    while done(it) < len(ps) and sent < LIMIT:
        n = done(it)
        if (it['id'], n) in HOLD:
            byid[it['id']]['thread_tweet_ids'].append('held'); print('HELD', it['id'], f'part {n+1}', flush=True); continue
        if sent: time.sleep(65)
        body = {'text': ps[n]}
        if n:
            p = byid[it['id']]
            body['reply'] = {'in_reply_to_tweet_id': last_id(p)}
        img_used = False
        if wants_card(it, n):
            try:
                mid = x.upload(card.render(it, f"/tmp/card_{it['id']}.png"))
            except Exception as e:
                print('CARD_FAIL', it['id'], repr(e)[:200], flush=True); mid = None
            if mid:
                body['media'] = {'media_ids': [mid]}; img_used = True
        st, resp = x.call('POST', 'https://api.x.com/2/tweets', body)
        if st != 201:
            print('ERROR', it['id'], f'part {n+1}/{len(ps)}', st, resp); raise SystemExit(1)
        tid = json.loads(resp)['data']['id']; sent += 1
        now = datetime.datetime.now(zoneinfo.ZoneInfo('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M')
        if n == 0:
            p = {'id': it['id'], 'posted_ist': now, 'tweet_id': tid}
            if img_used: p['image'] = True; carded += 1
            if len(ps) > 1: p['thread_tweet_ids'] = [tid]
            posted.append(p); byid[it['id']] = p
        else:
            p = byid[it['id']]
            p['thread_tweet_ids'] = (p.get('thread_tweet_ids') or [p['tweet_id']]) + [tid]
            p['posted_ist'] = p['posted_ist'] or now
        save(f"Poster: record {it['id']} part {n+1}/{len(ps)}")
        print('OK' + (' +IMG' if img_used else ''), it['id'], f'{n+1}/{len(ps)}', now, tid, '|', it['headline'][:70], flush=True)
    if sent >= LIMIT: break
left = sum(len(parts(i)) - done(i) for i in queue)
print('REMAINING_PARTS', left)
