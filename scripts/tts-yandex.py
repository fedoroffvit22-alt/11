import json,subprocess,base64,sys,os
def synth(out,text,voice,role=None,speed=1.0):
    hints=[{"voice":voice}]+([{"role":role}] if role else [])+[{"speed":speed}]
    body=json.dumps({"text":text,"hints":hints,"outputAudioSpec":{"containerAudio":{"containerAudioType":"MP3"}},"loudnessNormalizationType":"LUFS"})
    for _ in range(3):
        r=subprocess.run(["curl","-sS","--max-time","28","-X","POST","https://tts.api.cloud.yandex.net/tts/v3/utteranceSynthesis","-H","Authorization: Api-Key proxy-injected","-H","Content-Type: application/json","-d",body],capture_output=True,text=True).stdout
        data=b''
        try:
            for line in r.splitlines():
                if line.strip(): data+=base64.b64decode(json.loads(line)["result"]["audioChunk"]["data"])
        except Exception as e:
            err=r[:200]; continue
        if len(data)>2000: open(out,'wb').write(data); return True
    print("FAIL",voice,role,err if 'err' in dir() else r[:200]); return False
if __name__=="__main__":
    T="Хозяин сам отключил сигнализацию. Даже для Москвы это было странно. Объект — стоматология на три кресла. План был простой. Забрать всё."
    os.makedirs('ya/proby',exist_ok=True)
    for v,r in [("alexander","neutral"),("alexander","good"),("kirill","strict"),("kirill","neutral"),("anton","neutral"),("ermil","neutral"),("zahar","neutral"),("madirus",None),("filipp",None)]:
        f=f"ya/proby/yandex-{v}{'-'+r if r else ''}.mp3"; print(v,r,synth(f,T,v,r,1.05))
