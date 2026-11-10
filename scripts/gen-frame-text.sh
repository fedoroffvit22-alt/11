#!/bin/bash
# text-only generation: gent.sh name size prompt
name=$1; size=$2; prompt=$3
for try in 1 2 3; do
python3 -I -c "import json,sys;print(json.dumps({'model':'gpt-image-2','size':sys.argv[1],'quality':'high','stream':True,'partial_images':2,'prompt':sys.argv[2]}))" "$size" "$prompt" > out/$name.req
curl -sS -N --max-time 400 https://api.openai.com/v1/images/generations -H "Authorization: Bearer proxy-injected" -H "Content-Type: application/json" -d @out/$name.req -o out/$name.sse
python3 -I - "$name" <<'P' && break
import json,base64,sys
n=sys.argv[1]; ok=False
for line in open(f'out/{n}.sse',errors='ignore'):
    if line.startswith('data: '):
        try: d=json.loads(line[6:])
        except Exception: continue
        if d.get('type','').endswith('completed'):
            open(f'out/{n}.png','wb').write(base64.b64decode(d['b64_json'])); ok=True; print(n,'ok')
if not ok: print(n,'ERR',open(f'out/{n}.sse',errors='ignore').read()[:300]); sys.exit(1)
P
sleep 5; done; rm -f out/$name.sse out/$name.req
