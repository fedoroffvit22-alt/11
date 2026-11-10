import json,subprocess,os,textwrap,math
from PIL import Image,ImageDraw,ImageFont
A='/home/user/11/assets/'; EP='ograblenie'; W,H=1080,1920; FPS=24
FB='/usr/share/fonts/opentype/inter/Inter-Bold.otf'; FX='/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf'
ORANGE='#FE9600'; GRAPH='#2B2B2E'; BEAT=60/112.35
def q(x,mn=2): return max(mn,math.ceil(x/BEAT-0.05))
def dur(f): return float(subprocess.run(['ffprobe','-v','0','-show_entries','format=duration','-of','csv=p=0',f],capture_output=True,text=True).stdout)
def run(a): subprocess.run(['ffmpeg','-y','-v','error']+a,check=True)
L={n:(who,text) for n,who,slot,text in json.load(open('lines.json'))[EP]}
def vfile(sid):
    who=L[sid][0]
    if who=='R': return f'voice3/{sid}-R_n.mp3'
    if sid=='12': return 'vid/b12_fast.mp3'
    return A+f'{EP}/golos/{sid}-{who}.mp3'
TITLES={'05':('ЮРИСТ','Вскроет любой\nдоговор аренды'),'06':('БУХГАЛТЕР','Берёт всю выручку.\nЗа двенадцать месяцев.\nНа проверку'),'07':('ИНЖЕНЕР','Знает, сколько на самом\nделе лет рентгену')}
ORDER=['00','01','02','03','04','05','06','07','08','09','10','11','12','13','14','15','16','17','18','19','20']
FACEY={'02':0.18,'05':0.12,'06':0.2,'07':0.12,'10':0.1,'11':0.2,'12':0.2,'15':0.15,'16':0.25,'17':0.08,'18':0.08}
def sub_png(text,path):
    im=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(im); f=ImageFont.truetype(FX,60)
    t='\n'.join(textwrap.wrap(text,24)); d.multiline_text((W//2,1340),t,font=f,fill='white',anchor='ma',align='center',spacing=14,stroke_width=6,stroke_fill='black'); im.save(path)
def title_png(name,body,path):
    im=Image.new('RGBA',(W,H),(0,0,0,120)); d=ImageDraw.Draw(im); f1=ImageFont.truetype(FX,104); f2=ImageFont.truetype(FB,58)
    w=d.textlength(name,font=f1); d.rectangle((90,800,90+w+60,800+140),fill=ORANGE); d.text((120,812),name,font=f1,fill=GRAPH)
    d.multiline_text((95,975),body,font=f2,fill='white',spacing=16,stroke_width=3,stroke_fill='black'); im.save(path)
def card_png(text,path):
    im=Image.new('RGB',(W,H),GRAPH); d=ImageDraw.Draw(im); f=ImageFont.truetype(FX,128)
    d.multiline_text((W//2,H//2),text,font=f,fill='white',anchor='mm',align='center',spacing=30); d.rectangle((440,H//2+200,640,H//2+216),fill=ORANGE); im.save(path)
ENC=['-c:v','libx264','-preset','medium','-crf','19','-pix_fmt','yuv420p','-r',str(FPS),'-an']
base=f"scale={W}:{H},setsar=1,fps={FPS}"
def punch(fy): 
    z=1.22; return f"scale={int(W*z)}:{int(H*z)},crop={W}:{H}:{int(W*(z-1)/2)}:{int(H*(z-1)*fy)}"
segs=[]; voice=[]; sfx=[]; t=0.0; plan=[]
def render(sid,src,vf,nb,ov,cuts=None,fy=0.3):
    d=nb*BEAT; out=f'cut2/{sid}.mp4'
    inputs=(['-loop','1','-t',f'{d+0.5:.2f}','-i',src[-1]] if src[0]=='-loop' else list(src))
    if cuts:
        en='+'.join(f"between(t,{a*BEAT:.3f},{b*BEAT:.3f})" for a,b in cuts)
        fc=f"[0:v]{vf},split=2[w][p0];[p0]{punch(fy)}[p];[w][p]overlay=enable='{en}'[c]"; last='c'
    else:
        fc=f"[0:v]{vf}[w]"; last='w'
    for i,(p,a,b) in enumerate(ov):
        inputs+=['-loop','1','-t',f'{d+0.5:.2f}','-i',p]; fc+=f";[{last}][{i+1}:v]overlay=enable='between(t,{a:.2f},{b:.2f})'[o{i}]"; last=f'o{i}'
    run(inputs+['-filter_complex',fc,'-map',f'[{last}]','-t',f'{d:.4f}','-threads','2']+ENC+[out]); return d
def intro_png(n,path):
    im=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(im)
    f0=ImageFont.truetype(FB,44); f1=ImageFont.truetype(FX,84); f2=ImageFont.truetype(FX,150); f3=ImageFont.truetype(FX,110)
    d.text((W//2,1010),'БИЗНЕС МАРКЕТ ПРЕДСТАВЛЯЕТ',font=f0,fill='white',anchor='mm',stroke_width=3,stroke_fill='black')
    d.text((W//2,1150),'САМОЕ ЗАКОННОЕ',font=f1,fill='white',anchor='mm',stroke_width=5,stroke_fill='black')
    if n>=2:
        d.rectangle((30,1230,W-30,1430),fill=ORANGE); d.text((W//2,1330),'ОГРАБЛЕНИЕ',font=f2,fill=GRAPH,anchor='mm')
    if n>=3: d.text((W//2,1520),'МОСКВЫ',font=f3,fill='white',anchor='mm',stroke_width=5,stroke_fill='black')
    im.save(path)
for sid in ORDER:
    ov=[]; vd=0
    if sid in L:
        vd=dur(vfile(sid)); off=0.0 if sid in('11','12') else 0.12
        voice.append((vfile(sid),t+off))
        if sid not in TITLES: p=f'cut2/sub_{sid}.png'; sub_png(L[sid][1].replace('«','').replace('»',''),p); ov.append((p,off,off+vd))
    if sid=='00':
        for n in (1,2,3): intro_png(n,f'cut2/intro{n}.png')
        d=render(sid,['-i','vid/17.mp4'],f"{base},setpts=PTS*1.5,eq=brightness=-0.10:saturation=0.6",5,[('cut2/intro1.png',0,BEAT),('cut2/intro2.png',BEAT,2*BEAT),('cut2/intro3.png',2*BEAT,99)])
        for k in range(3): sfx.append(('vid/hit.mp3',t+k*BEAT,1.0))
    elif sid=='03':
        nb=3; run(['-i','vid/01.mp4','-i','vid/02.mp4','-filter_complex',f"[0:v]{base}[a];[1:v]{base}[b];[a][b]concat=n=2:v=1[c];[c]trim=0:8,setpts=PTS-STARTPTS,reverse,setpts=PTS/5[o]",'-map','[o]','-t',f'{nb*BEAT:.3f}']+ENC+['cut2/03raw.mp4'])
        im=Image.new('RGBA',(W,H),(0,0,0,90)); dd=ImageDraw.Draw(im); f=ImageFont.truetype(FX,92); dd.multiline_text((W//2,H//2),'ДВУМЯ НЕДЕЛЯМИ\nРАНЕЕ',font=f,fill='white',anchor='mm',align='center',spacing=24,stroke_width=5,stroke_fill='black'); im.save('cut2/t03.png')
        d=render(sid,['-i','cut2/03raw.mp4'],'null',nb,[('cut2/t03.png',0,9)]); sfx.append(('vid/rewind.mp3',t,0.9))
    elif sid in('08','14'):
        nb=3; card_png({'08':'ДО ДЕЛА —\n14 ДНЕЙ','14':'ДЕНЬ ДЕЛА'}[sid],f'cut2/card_{sid}.png'); d=render(sid,['-loop','1','-i',f'cut2/card_{sid}.png'],base,nb,[]); sfx.append(('vid/hit.mp3',t,1.0)); sfx.append(('vid/whoosh.mp3',t+nb*BEAT-0.35,0.7))
    elif sid=='09':
        nb=q(vd+0.3,8); bs=[nb//4+(1 if i<nb%4 else 0) for i in range(4)]
        parts=''.join(f"[{i}:v]{base},setpts=PTS/1.5,trim=0.2:{0.2+bs[i]*BEAT:.3f},setpts=PTS-STARTPTS[p{i}];" for i in range(4))
        run(['-i','vid/09a.mp4','-i','vid/09b.mp4','-i','vid/09c.mp4','-i','vid/09d.mp4','-filter_complex',parts+"[p0][p1][p2][p3]concat=n=4:v=1[o]",'-map','[o]','-t',f'{nb*BEAT:.3f}']+ENC+['cut2/09raw.mp4'])
        d=render(sid,['-i','cut2/09raw.mp4'],'null',nb,ov); c=0
        for b in bs: sfx.append(('vid/whoosh.mp3',t+c*BEAT-0.1,0.5)); c+=b
    elif sid=='19':
        nb=5; d=render(sid,['-loop','1','-i',A+'brand/plashka-kupit.png'],base,nb,[]); sfx.append(('vid/hit.mp3',t,1.0))
    elif sid=='20':
        nb=q(vd+0.4); d=render(sid,['-loop','1','-i',A+'naslednik/kadry-9x16/kadr-02.jpg'],f"{base},zoompan=z='min(1+0.0012*on,1.2)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}",nb,ov)
    elif sid in TITLES:
        nb=q(vd+0.3,5); fr=2*BEAT; p=f'cut2/title_{sid}.png'; title_png(*TITLES[sid],p)
        d=render(sid,['-i',f'vid/{sid}.mp4'],f"{base},setpts=PTS/1.4,trim=0:{fr:.3f},tpad=stop_mode=clone:stop_duration=12",nb,[(p,fr,99)]+ov,cuts=[(2,99)],fy=FACEY.get(sid,0.3)); sfx.append(('vid/hit.mp3',t+fr,1.0))
        voice[-1]=(voice[-1][0],t+fr+0.05)
    else:
        src={'11':'vid/11_sync.mp4','12':'vid/12_sync.mp4'}.get(sid,f'vid/{sid}.mp4')
        if sid in('11','12'):
            nb=q(vd+0.25); sp=1.0; step=4
        else:
            nb=q(vd+0.3,4) if sid in L else 4; sp=max(1.0,min(1.5,5.0/(nb*BEAT+0.05))); step=2
        cuts=[(a,min(a+step,nb)) for a in range(step,nb,2*step)] if nb>=4 else None
        d=render(sid,['-i',src],f"{base},setpts=PTS/{sp:.3f},tpad=stop_mode=clone:stop_duration=6",nb,ov,cuts=cuts,fy=FACEY.get(sid,0.3))
        if sid=='01': sfx.append(('vid/beep.mp3',t+0.1,0.8))
        if sid=='17': sfx.append(('vid/hit.mp3',t,0.9))
    segs.append(f'cut2/{sid}.mp4'); plan.append((sid,round(t,2),round(d,2))); t+=d
open('cut2/list.txt','w').write(''.join(f"file '{os.path.abspath(s)}'\n" for s in segs))
run(['-f','concat','-safe','0','-i','cut2/list.txt','-c','copy','cut2/video.mp4'])
def mix(items,out):
    inp=[]; fl=[]
    for i,it in enumerate(items):
        f,o=it[0],max(it[1],0); v=it[2] if len(it)>2 else 1.0
        inp+=['-i',f]; fl.append(f"[{i}]volume={v},adelay={int(o*1000)}:all=1[a{i}]")
    fc=';'.join(fl)+';'+''.join(f'[a{i}]' for i in range(len(fl)))+f"amix=inputs={len(fl)}:normalize=0,apad=whole_dur={t:.3f},atrim=0:{t:.3f}[o]"
    run(inp+['-filter_complex',fc,'-map','[o]','-ar','44100','-ac','2',out])
mix(voice,'cut2/voice.wav'); mix(sfx,'cut2/sfx.wav')
run(['-ss','0.07','-i','vid/music.mp3','-t',f'{t:.3f}','-af',f"volume=0.9,afade=t=out:st={t-1.8:.2f}:d=1.8",'-ar','44100','-ac','2','cut2/music.wav'])
run(['-i','cut2/music.wav','-i','cut2/voice.wav','-i','cut2/sfx.wav','-filter_complex',
 "[1]asplit=3[v1][v2][v3];[0]volume=0.7[m0];[m0][v1]sidechaincompress=threshold=0.012:ratio=14:attack=10:release=400:makeup=1[m];[m]asplit=2[mm][md];[v2]volume=1.7[vv];[2]volume=0.8[s];[mm][vv][s]amix=inputs=3:normalize=0,alimiter=limit=0.95[o];[v3]anullsink",
 '-map','[o]','-c:a','aac','-b:a','192k','cut2/audio.m4a','-map','[md]','cut2/music_ducked.wav'])
os.makedirs(A+f'{EP}/video',exist_ok=True)
run(['-i','cut2/video.mp4','-i','cut2/audio.m4a','-c:v','libx264','-preset','medium','-crf','24','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart','-shortest',A+f'{EP}/video/chernovik-2.mp4'])
json.dump(plan,open('cut2/plan.json','w')); print('total',round(t,1)); print(plan)
