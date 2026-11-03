# Локации

Мастер-кадр — одна утверждённая картинка локации. Её прикладывают как образец ко всем клипам в этом месте, чтобы двор, мойка и переговорная не менялись от кадра к кадру. Всего мастеров 9; дача и окно Петровны встречаются по одному разу и мастера не требуют.

## Схема двора

Двор — главная локация: в нём проходят 6 сцен из 12. Схема нужна, чтобы «Волга», будка и спуск на мойку не переезжали между кадрами.

```
                  ДОМ 2   [4] спуск на мойку в цоколе
            ┌──────────────────────────────────────────┐
            └────────────────────▲─────────────────────┘
                                 │
                                 │ [3] проезд:            ┃ ДОМ 1
                                 │     очередь            ┃
                                 │     из трёх машин      ┃ [7] подъезд
                                 │               [6] «Волга»
                                 │                        ┃
  [2] забор с баннером           │                        ┃ окно Петровны
  «ДВОР БЕЗ МАШИН»               │                        ┃ (3-й этаж),
 ════════════════════════════════╪═ [1] шлагбаум, будка ══┃ над будкой
                                 │
                               УЛИЦА
             [5] белый каршеринг Артёма — на той стороне улицы
```

**Правила, которые нельзя нарушать:**
- Машина въезжает с улицы (на схеме снизу вверх) и едет по проезду прямо к спуску на мойку.
- Дом 1 и «Волга» — справа по ходу движения. Поэтому в сцене 2 Вера видит «Волгу» из правого, пассажирского, окна.
- Баннер «ДВОР БЕЗ МАШИН» висит на заборе слева от въезда, лицом во двор.
- Будка — справа от стрелы, у торца дома 1. Окно Петровны прямо над будкой.
- «Волга» всегда на одном месте: у подъезда дома 1, капотом к проезду.
- Задний двор с канистрами — за домом 2, из двора его не видно.

## Точки камер

| Точка | Где стоит камера и что видно | Клипы |
|---|---|---|
| **К1** | На въезде со стороны улицы, на уровне бампера: стрела поперёк кадра, за ней двор | 01-02, 12-07 |
| **К1-обр.** | Со стороны двора, через лобовое стекло машины, стоящей у стрелы | 01-03 |
| **К2** | Из глубины двора, от спуска, на въезд: очередь на проезде, шлагбаум; дом 1 — слева в кадре, баннер — справа | 02-01 |
| **К3** | «Субботний мастер»: сбоку от спуска, смотрит на дом 1. На переднем плане у спуска — мужчины, на заднем — «Волга» у подъезда и Петровна | 05-03, повтор в 09-07 |
| **К4** | Сбоку от въезда, со стороны двора: шлагбаум, будка, машина у стрелы, Петровна | 01-04, 08-01, сцены 8 и 10 |
| **К5** | С той стороны улицы, из каршеринга: шлагбаум, въезжающие машины, свет мойки в глубине | 03-01 |
| **К6** | У подъезда дома 1: «Волга» средним и крупным планом | 09-01, 09-02, 12-02 |

---

## L1. Двор ЖК (мастера 1–3)

**Мастер 1 — двор, пасмурный день** (`loc_yard_v1.png`):

```
wide establishing shot of a modern Moscow residential complex courtyard, 12-to-17-storey beige and grey towers, a black metal fence with a large blank white banner, {BARRIER} at the street entrance, a driveway leading to a ramp that descends into an underground car wash under the far building, a black GAZ-24 Volga parked by a building entrance, wet grey slush, bare trees, {STYLE}
```

Состояния света — менять только погоду, геометрию не трогать:
- серый день — сцены 1, 8, 9, 10 (как в мастере);
- утро, слякоть, морось — сцена 2 (`light drizzle, early morning`);
- пасмурная суббота, асфальт подсох — сцена 5 (`dry asphalt, overcast morning`).

**Мастер 2 — двор, морозное солнце** (`loc_yard_sun_v1.png`, только сцена 12): тот же запрос, но `{STYLE}` в финальном варианте, плюс `frost on the railings, clean dry asphalt`.

**Мастер 3 — въезд крупнее** (`loc_entrance_v1.png`, точки К1 и К4):

```
the street entrance of a residential courtyard: {BARRIER}, a black metal fence, a 17-storey tower right behind the booth, slush on the asphalt, {STYLE}
```

## L2. Мойка (мастера 4–6)

**Мастер 4 — бокс ночью** (`loc_bay_night_v1.png`, сцена 2):

```
night inside a small contact car wash bay, wet tiled floor with a long drainage pit under a removable steel grate, pressure washer hoses on the wall, fluorescent tube lights, foam residue, steam, {STYLE}
```

(В `{STYLE}` — ночной вариант.)

**Мастер 5 — задний двор с канистрами** (`loc_backyard_v1.png`, сцена 6):

```
narrow back yard behind a car wash, grey concrete wall, a towering wall of empty blue 20-liter plastic jerrycans stacked higher than a person, puddles, {STYLE}
```

**Мастер 6 — каморка-офис** (`loc_office_v1.png`, сцена 11):

```
tiny cluttered office of a car wash, white plastic table and two plastic chairs, an electric kettle, mugs, a wall calendar from a car chemicals supplier, a small window looking into the wash bay, fluorescent light, {STYLE}
```

## L3. Сити (мастера 7–8)

**Мастер 7 — переговорная** (`loc_meeting_v1.png`, сцена 4):

```
glass meeting room on the 62nd floor of a modern skyscraper, floor-to-ceiling windows streaked with rain, other glass towers outside in grey mist, long white glossy table, black leather chairs, a small tablet screen by the glass door, no logos, {STYLE}
```

Башни — безымянные, без узнаваемых логотипов и надписей.

**Мастер 8 — лифт** (`loc_elevator_v1.png`, сцена 5):

```
mirrored elevator interior with brushed steel doors, infinite reflections, cool white light, seen from the lobby through the open doors, {STYLE}
```

## L4. Салон каршеринга ночью (мастер 9)

**Мастер 9** (`loc_car_night_v1.png`, сцена 3):

```
night interior of a white compact sedan parked on a Moscow street, rain streaming down the windshield, sodium street lights outside, a phone holder on the dashboard, {STYLE}
```

(В `{STYLE}` — ночной вариант.)

## Разовые места без мастера

- **Окно Петровны снаружи** (07-02): `third-floor window of a residential tower seen from outside, white lace curtains, a framed black-and-white photo on the windowsill, overcast`.
- **Дача** (12-01): `cozy old wooden dacha living room, soft morning light through lace curtains, an old sofa with a knitted blanket, a small side table`, свет тёплый.
- **Ванная** (07-01): у Артёма — светлая плитка, у Гены — старая зелёная плитка и маленькое зеркало. Разница в достатке видна без слов.
