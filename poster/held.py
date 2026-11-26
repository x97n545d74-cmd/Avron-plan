import json, sys, subprocess
sys.path.insert(0, sys.argv[1]); import x
D='avron-x-merger/'
q={json.loads(l)['id']:json.loads(l) for l in open(D+'queue.jsonl') if l.strip()}
it=q['20261117-1301-T01']; text=it['thread'][1]
posted=[json.loads(l) for l in open(D+'posted.jsonl') if l.strip()]
p=next(e for e in posted if e['id']==it['id'])
st,resp=x.call('POST','https://api.x.com/2/tweets',{'text':text,'reply':{'in_reply_to_tweet_id':p['thread_tweet_ids'][-1]}})
if st!=201: print('ERROR',st,resp); raise SystemExit(1)
tid=json.loads(resp)['data']['id']
p['thread_tweet_ids'][p['thread_tweet_ids'].index('held')]=tid
open(D+'posted.jsonl','w').write(''.join(json.dumps(e)+'\n' for e in posted))
msg="Poster: post held part 2 of 20261117-1301-T01 (user approved)\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01Ns1uU9PFXc9m84zBiLW7x1"
for a in (['add',D+'posted.jsonl'],['commit','-m',msg],['pull','--rebase','origin','avron-x-merger'],['push','-u','origin','avron-x-merger']):
    subprocess.run(['git',*a],check=True,capture_output=True)
print('OK',tid,'|',text[:90].replace('\n',' '))
