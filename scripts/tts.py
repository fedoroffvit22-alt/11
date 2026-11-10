import json,subprocess,sys,os,concurrent.futures as cf
RU="Speak Russian like a native Moscow speaker, natural pronunciation and stress. "
V={
"R":("onyx",RU+"Narrator of a Guy Ritchie-style crime comedy: low, dry, deadpan, slightly amused, brisk energetic pace, only very short pauses between sentences. No smiling in the voice."),
"Rwarm":("onyx",RU+"Narrator of a warm family story: low, calm, gentle, restrained, steady natural pace, short pauses."),
"broker":("ash",RU+"Calm, confident business broker, quiet dry irony, speaks to the point at a natural brisk pace."),
"accountant":("fable",RU+"Elderly sceptical accountant asking a practical question, slightly grumpy."),
"gena":("echo",RU+"Tired fifty-year-old car mechanic, gruff, low energy, sincere."),
"gena_robot":("echo",RU+"Completely flat, monotone, like an answering machine, no emotion at all."),
"buyer1":("verse",RU+"Friendly curious man in his thirties, asks quietly, half-smiling."),
"caller1":("verse",RU+"Cheerful pushy man on the phone, fast."),
"caller2":("fable",RU+"Overconfident man on the phone, businesslike, fast."),
"caller3":("ballad",RU+"Slick real estate agent on the phone, self-important."),
"caller4":("coral",RU+"Suspicious woman on the phone, interrogating tone."),
"palych":("ballad",RU+"Sixty-year-old gruff father, low rough voice, speaks quietly at a natural pace, hiding emotion."),
"palych_whisper":("ballad",RU+"Sixty-year-old gruff man whispering in a concert hall, proud, very quiet."),
"rinat":("verse",RU+"Calm confident mechanic, says one word with certainty."),
}
def tts(out,voice,instr,text):
    body=json.dumps({"model":"gpt-4o-mini-tts","voice":voice,"input":text,"instructions":instr,"response_format":"mp3"})
    for _ in range(3):
        subprocess.run(["curl","-sS","--max-time","28","https://api.openai.com/v1/audio/speech","-H","Authorization: Bearer proxy-injected","-H","Content-Type: application/json","-d",body,"-o",out])
        if os.path.exists(out) and open(out,'rb').read(3) in (b'ID3',b'\xff\xf3\xe4',b'\xff\xfb\x90') or (os.path.exists(out) and os.path.getsize(out)>4000): return True
    print("FAIL",out,open(out,'rb').read(200)); return False
if __name__=="__main__":
    L=json.load(open(os.path.join(os.path.dirname(__file__),'voice-lines.json'))); jobs=[]
    for ep,ls in L.items():
        os.makedirs(f'voice/{ep}',exist_ok=True)
        for n,who,slot,text in ls:
            v,i=V[who]; jobs.append((f'voice/{ep}/{n}-{who}.mp3',v,i,text))
    for v in ["onyx","ash","echo","ballad"]:
        os.makedirs('voice/proby',exist_ok=True)
        jobs.append((f'voice/proby/rasskazchik-{v}.mp3',v,V["R"][1],"Хозяин сам отключил сигнализацию. Даже для Москвы это было странно. Объект — стоматология на три кресла. План был простой. Забрать всё."))
    with cf.ThreadPoolExecutor(8) as ex: print(sum(ex.map(lambda j:tts(*j),jobs)),'of',len(jobs))
