"""Фото квартиры для Циана через GPT Image.

Берёт 3D-рендеры из photos/render/ (точная геометрия по планировке лота 142)
и просит GPT Image сделать из каждого фотореалистичный кадр, ничего не двигая.
В качестве образца отделки Greystone прикладывает рендеры застройщика.

Нужно один раз:
  1) в настройках окружения добавить домен api.openai.com в Network access;
  2) там же добавить секрет / переменную OPENAI_API_KEY со своим ключом.
Запуск:  python3 tools/gpt_photos.py            (все 10 кадров)
         python3 tools/gpt_photos.py 1 4 9      (только выбранные)
Результат: photos/gpt/NN-название.jpg
Модель можно сменить переменной OPENAI_IMAGE_MODEL (по умолчанию gpt-image-1).
"""
import base64, io, json, os, sys, time, uuid, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'photos', 'render')
OUT = os.path.join(ROOT, 'photos', 'gpt')
REF = [os.path.join(ROOT, 'landing', 'img', f) for f in ('finish-kitchen-1400.webp', 'finish-bath-1400.webp')]
MODEL = os.environ.get('OPENAI_IMAGE_MODEL', 'gpt-image-1')
KEY = os.environ.get('OPENAI_API_KEY', '').strip()

FINISH = ("Отделка Greystone по договору: ламинат светлый серо-бежевый дуб, стены под окраску тёплого светло-серого цвета, "
          "белый матовый натяжной потолок, межкомнатные двери МДФ светло-серые с чёрными ручками, белые подоконники, "
          "окна в графитовых рамах. Санузел: крупноформатная бежевая плитка под мрамор на стенах и полу, белая ванна со "
          "стеклянной шторкой, подвесной унитаз, белая подвесная тумба, чёрные смесители, чёрный полотенцесушитель.")

SHOTS = {
    1: ('kuhnya-stolovaya', 'Кухня-столовая 14 м²: угловая кухня с серыми фасадами без ручек и пеналом под дерево, светлая столешница под мрамор, круглый обеденный стол у окна, тюль и серые шторы.'),
    2: ('kuhnya-rabochaya-zona', 'Кухня 14 м², вид от окна на рабочую зону и пенал со встроенной духовкой.'),
    3: ('kuhnya-stoleshnica', 'Деталь кухни: столешница и фартук под светлый мрамор, мойка, чёрный смеситель, подсветка под верхними шкафами.'),
    4: ('spalnya-16', 'Спальня 16,4 м²: двуспальная кровать с серым мягким изголовьем, тумбы из дуба, шкаф в нише, кресло у окна, ковёр.'),
    5: ('spalnya-16-okna', 'Спальня 16,4 м², угловая комната с двумя окнами, дневной свет.'),
    6: ('komnata-13', 'Комната 13,5 м²: кровать, шкаф до потолка, рабочий стол у окна.'),
    7: ('komnata-13-rabochee-mesto', 'Комната 13,5 м²: рабочее место у окна, монитор, кресло.'),
    8: ('prihozhaya', 'Прихожая 9,4 м²: шкаф-купе во всю стену, светлый ковёр, входная дверь, точечные светильники.'),
    9: ('sanuzel', 'Санузел 4,5 м²: ванна со шторкой, подвесная тумба с раковиной и зеркалом с подсветкой.'),
    10: ('sanuzel-tumba-vanna', 'Санузел 4,5 м²: тумба, зеркало, ванна, полотенцесушитель.'),
}

PROMPT = ("Сделай из первого изображения профессиональную интерьерную фотографию для объявления о продаже квартиры: "
          "снято на полнокадровую камеру, объектив 16–24 мм, вертикали ровные, мягкий дневной свет из окна, естественные "
          "тени, реальные текстуры дерева, ткани и камня, без глянца компьютерной графики. СТРОГО сохрани планировку, "
          "положение и размеры окон, дверей, стен, кухни, сантехники и мебели, ракурс камеры и пропорции комнаты — "
          "ничего не добавляй и не убирай из архитектуры. Цвета и материалы отделки сверяй с остальными изображениями-образцами. "
          "{finish} Кадр: {shot} Без людей, без текста, без водяных знаков.")


def multipart(fields, files):
    b = uuid.uuid4().hex
    buf = io.BytesIO()
    for k, v in fields.items():
        buf.write(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, (fn, data, ct) in files:
        buf.write(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\nContent-Type: {ct}\r\n\r\n'.encode())
        buf.write(data); buf.write(b'\r\n')
    buf.write(f'--{b}--\r\n'.encode())
    return buf.getvalue(), f'multipart/form-data; boundary={b}'


def as_png(path):
    from PIL import Image
    im = Image.open(path).convert('RGB')
    im.thumbnail((1536, 1536))
    out = io.BytesIO(); im.save(out, 'PNG'); return out.getvalue()


def call(i):
    slug, shot = SHOTS[i]
    base = os.path.join(SRC, f'{i:02d}-{slug}.jpg')
    if not os.path.exists(base):
        print(f'[{i}] нет исходного рендера {base}'); return False
    files = [('image[]', (f'{i:02d}.png', as_png(base), 'image/png'))]
    for r in REF:
        if os.path.exists(r):
            files.append(('image[]', (os.path.basename(r) + '.png', as_png(r), 'image/png')))
    fields = {'model': MODEL, 'prompt': PROMPT.format(finish=FINISH, shot=shot), 'size': '1536x1024', 'quality': 'high', 'n': '1'}
    if MODEL.startswith('gpt-image'):
        fields['input_fidelity'] = 'high'
    body, ct = multipart(fields, files)
    req = urllib.request.Request('https://api.openai.com/v1/images/edits', data=body, method='POST',
                                 headers={'Authorization': f'Bearer {KEY}', 'Content-Type': ct})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.load(r)
            img = base64.b64decode(data['data'][0]['b64_json'])
            os.makedirs(OUT, exist_ok=True)
            from PIL import Image
            out = os.path.join(OUT, f'{i:02d}-{slug}.jpg')
            Image.open(io.BytesIO(img)).convert('RGB').save(out, 'JPEG', quality=93, subsampling=0)
            print(f'[{i}] готово: {out}'); return True
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors='replace')[:400]
            print(f'[{i}] ошибка API {e.code}: {msg}')
            if e.code in (400, 401, 403): return False
        except Exception as e:
            print(f'[{i}] сбой: {e}')
        time.sleep(5 * (attempt + 1))
    return False


if __name__ == '__main__':
    if not KEY:
        sys.exit('Нет OPENAI_API_KEY. Добавьте его в настройках окружения и запустите новую сессию.')
    ids = [int(a) for a in sys.argv[1:]] or list(SHOTS)
    ok = sum(call(i) for i in ids)
    print(f'Готово {ok} из {len(ids)}. Папка: {OUT}')
