import json,subprocess,os,textwrap
from PIL import Image,ImageDraw,ImageFont
A='/home/user/11/assets/'; EP='ograblenie'; W,H=1080,1920; FPS=24
FB='/usr/share/fonts/opentype/inter/Inter-Bold.otf'; FX='/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf'
ORANGE='#FE9600'; GRAPH='#2B2B2E'
T=json.load(open('timing.json'))[EP]['rows']
shots=[(r[0],r[3]) for r in T if r[1]=='shot']; lines={}
for r in T:
    if r[1]!='shot': lines.setdefault(r[0],[]).append([r[2],r[3],r[4]])
def dur(f): return float(subprocess.run(['ffprobe','-v','0','-show_entries','format=duration','-of','csv=p=0',f],capture_output=True,text=True).stdout)
# voice files; broker replaced by cloned voice
def vfile(sid,who):
    if who=='broker' and sid=='12': return 'vid/b12_n.mp3'
    return A+f'{EP}/golos/{sid}-{who}.mp3'
TITLES={'05':('ЮРИСТ','Вскроет любой\nдоговор аренды'),'06':('БУХГАЛТЕР','Берёт всю выручку.\nЗа двенадцать месяцев.\nНа проверку'),'07':('ИНЖЕНЕР','Знает, сколько на самом\nделе лет рентгену')}
CARDS={'08':'ДО ДЕЛА —\n14 ДНЕЙ','14':'ДЕНЬ ДЕЛА'}
def sub_png(text,path):
    im=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(im); f=ImageFont.truetype(FB,54)
    t='\n'.join(textwrap.wrap(text,26)); d.multiline_text((W//2,1420),t,font=f,fill='white',anchor='ma',align='center',spacing=14,stroke_width=5,stroke_fill='black'); im.save(path)
def title_png(name,body,path):
    im=Image.new('RGBA',(W,H),(0,0,0,110)); d=ImageDraw.Draw(im); f1=ImageFont.truetype(FX,96); f2=ImageFont.truetype(FB,56)
    w=d.textlength(name,font=f1); d.rectangle((90,820,90+w+60,820+130),fill=ORANGE); d.text((120,832),name,font=f1,fill=GRAPH)
    d.multiline_text((95,985),body,font=f2,fill='white',spacing=16,stroke_width=3,stroke_fill='black'); im.save(path)
def card_png(text,path,bg=GRAPH):
    im=Image.new('RGB',(W,H),bg); d=ImageDraw.Draw(im); f=ImageFont.truetype(FX,120)
    d.multiline_text((W//2,H//2),text,font=f,fill='white',anchor='mm',align='center',spacing=30); d.rectangle((440,H//2+190,640,H//2+204),fill=ORANGE); im.save(path)
def run(a): subprocess.run(['ffmpeg','-y','-v','error']+a,check=True)
ENC=['-c:v','libx264','-preset','medium','-crf','20','-pix_fmt','yuv420p','-r',str(FPS),'-an']
segs=[]; audio=[]; t=0.0; plan=[]
for sid,d0 in shots:
    ls=lines.get(sid,[]); 
    for l in ls: l[1]=dur(vfile(sid,l[0]))
    need=sum(l[1] for l in ls)+0.3*max(len(ls)-1,0)+(0.6 if ls else 0)
    d=max(d0,round(need+0.49)); out=f'cut/{sid}.mp4'; ov=[]; off=0.3
    for who,ld,text in ls:
        p=f'cut/sub_{sid}_{len(ov)}.png'; sub_png(text,p); ov.append((p,off,off+ld)); audio.append((vfile(sid,who),t+off)); off+=ld+0.3
    if sid in TITLES:
        p=f'cut/title_{sid}.png'; title_png(*TITLES[sid],p); ov.insert(0,(p,1.6,d))
    base=f"scale={W}:{H},setsar=1,fps={FPS}"
    def with_ov(inputs,vf,d):
        fc=f"[0:v]{vf}[v0]"; last='v0'
        for i,(p,a,b) in enumerate(ov):
            inputs+=['-loop','1','-i',p]; fc+=f";[{last}][{i+1}:v]overlay=enable='between(t,{a:.2f},{b:.2f})'[v{i+1}]"; last=f'v{i+1}'
        run(inputs+['-filter_complex',fc,'-map',f'[{last}]','-t',str(d)]+ENC+[out])
    if sid in CARDS:
        card_png(CARDS[sid],f'cut/card_{sid}.png'); with_ov(['-loop','1','-i',f'cut/card_{sid}.png'],base,d)
    elif sid=='03':
        run(['-i','vid/01.mp4','-i','vid/02.mp4','-filter_complex',f"[0:v]{base}[a];[1:v]{base}[b];[a][b]concat=n=2:v=1[c];[c]trim=0:8,reverse,setpts=PTS/4[o]",'-map','[o]','-t','2']+ENC+['cut/03raw.mp4'])
        im=Image.new('RGBA',(W,H),(0,0,0,90)); dd=ImageDraw.Draw(im); f=ImageFont.truetype(FX,84); dd.multiline_text((W//2,H//2),'ДВУМЯ НЕДЕЛЯМИ\nРАНЕЕ',font=f,fill='white',anchor='mm',align='center',spacing=24,stroke_width=4,stroke_fill='black'); im.save('cut/t03.png'); ov.append(('cut/t03.png',0,2))
        with_ov(['-i','cut/03raw.mp4'],'null',d)
    elif sid=='09':
        parts=''.join(f"[{i}:v]{base},trim=0.4:{0.4+d/4:.3f},setpts=PTS-STARTPTS[p{i}];" for i in range(4))
        run(['-i','vid/09a.mp4','-i','vid/09b.mp4','-i','vid/09c.mp4','-i','vid/09d.mp4','-filter_complex',parts+"[p0][p1][p2][p3]concat=n=4:v=1[o]",'-map','[o]','-t',str(d)]+ENC+['cut/09raw.mp4'])
        with_ov(['-i','cut/09raw.mp4'],'null',d)
    elif sid=='19':
        with_ov(['-loop','1','-i',A+'brand/plashka-kupit.png'],base,d)
    elif sid=='20':
        with_ov(['-loop','1','-i',A+'naslednik/kadry-9x16/kadr-02.jpg'],f"{base},zoompan=z='min(1+0.0006*on,1.1)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}",d)
    else:
        k=min(max(d/5.0,1.0),1.3); pad=max(d-5.0*k,0)+0.2
        with_ov(['-i',f'vid/{sid}.mp4'],f"{base},setpts=PTS*{k:.3f},tpad=stop_mode=clone:stop_duration={pad:.2f}",d)
    segs.append(out); plan.append((sid,t,d)); t+=d
open('cut/list.txt','w').write(''.join(f"file '{os.path.abspath(s)}'\n" for s in segs))
run(['-f','concat','-safe','0','-i','cut/list.txt','-c','copy','cut/video.mp4'])
inp=[]; fl=[]
for i,(f,o) in enumerate(audio): inp+=['-i',f]; fl.append(f"[{i}]adelay={int(o*1000)}:all=1[a{i}]")
fc=';'.join(fl)+';'+''.join(f'[a{i}]' for i in range(len(fl)))+f"amix=inputs={len(fl)}:normalize=0,apad=whole_dur={t}[o]"
run(inp+['-filter_complex',fc,'-map','[o]','-c:a','aac','-b:a','160k','cut/voice.m4a'])
os.makedirs(A+f'{EP}/video',exist_ok=True)
run(['-i','cut/video.mp4','-i','cut/voice.m4a','-c:v','libx264','-preset','medium','-crf','25','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart','-shortest',A+f'{EP}/video/chernovik.mp4'])
json.dump(plan,open('cut/plan.json','w')); print('total',t)
