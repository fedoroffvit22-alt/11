#!/bin/bash
# usage: gen.sh name size prompt [image files...]   (default refs: 3 photos)
name=$1; size=$2; prompt=$3; shift 3
refs=("$@"); [ ${#refs[@]} -eq 0 ] && refs=(assets/broker/broker-sheet.jpg)
args=(); for f in "${refs[@]}"; do args+=(-F "image[]=@$f"); done
for try in 1 2 3; do
curl -sS -N --max-time 400 https://api.openai.com/v1/images/edits -H "Authorization: Bearer proxy-injected" \
 -F model=gpt-image-2 -F size=$size -F quality=${Q:-high} -F stream=true -F partial_images=2 "${args[@]}" -F "prompt=$prompt" -o out/$name.sse
python3 -I - "$name" <<'P' && break
import json,base64,sys
n=sys.argv[1]; ok=False
for line in open(f'out/{n}.sse',errors='ignore'):
    if line.startswith('data: '):
        try: d=json.loads(line[6:])
        except Exception: continue
        if d.get('type','').endswith('completed'):
            open(f'out/{n}.png','wb').write(base64.b64decode(d['b64_json'])); ok=True; print(n,'ok',d.get('usage',{}).get('total_tokens'))
if not ok: print(n,'ERR',open(f'out/{n}.sse',errors='ignore').read()[:300]); sys.exit(1)
P
sleep 5; done; rm -f out/$name.sse
