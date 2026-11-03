# Персонажи и реквизит

## Как пользоваться

1. Для каждого героя сгенерировать лист-референс по запросу ниже, выбрать лучший вариант и сохранить как `ref_<имя>_v1.png`.
2. Дальше прикладывать этот лист ко всем кадрам с героем (функция «референс персонажа» или «картинка-образец» в генераторе).
3. Текст из блока «Описание» вставлять в запросы `shotlist.md` вместо `{GENA}`, `{ARTEM}`, `{VERA}`, `{PETROVNA}`.
4. Цветовые якоря — жилетка хаки, синий костюм, горчичный шарф, бордовый берет — не менять ни в одном кадре. По ним зритель узнаёт героя даже на общем плане.

Запрос для листа-референса (одинаковый для всех, подставить описание героя):

```
character reference sheet of {CHARACTER}: front view, three-quarter view, side view, full body and close-up portrait, neutral light grey studio background, even soft light, consistent outfit, photorealistic, no text
```

---

## Гена — продавец, 52 года

**В кадре:** тяжёлый, быстрый, руки всё время заняты. Хитрый прищур, улыбается одной стороной рта.

**Описание `{GENA}`:**

```
Gena, a stocky 52-year-old Russian man with a grey buzz cut and short grey stubble, weathered ruddy face, sly squint, wearing a quilted khaki-green vest over a navy hoodie and black rubber boots
```

**Костюм по сценам:**
- Сцены 2, 4–6, 8–9, 11 — основной: жилетка хаки, синее худи, резиновые сапоги, тяжёлая связка ключей с красным брелоком. Щетина есть всегда.
- Сцена 4 (Сити) — то же, плюс клок белой пены на рукаве жилетки.
- Сцена 7 (у зеркала) — синее худи без жилетки.
- Сцена 12 (дача) — выцветшая серая футболка, тренировочные штаны, шерстяные носки.

**Выражения для генерации:** самодовольная улыбка; возмущение с выпученными глазами; медленное осознание вины.

---

## Артём — покупатель, 33 года

**В кадре:** прямая спина, короткие точные движения. Когда считает в уме, поправляет очки.

**Описание `{ARTEM}`:**

```
Artem, a slim 33-year-old Russian man with neat dark side-parted hair, thin silver wire-rim glasses and a clean-shaven face, wearing a slim navy suit, a white shirt and a black wool coat
```

**Костюм по сценам:**
- Сцены 1, 6, 8, 9 и суббота во дворе в сцене 5 — костюм и чёрное пальто.
- Сцена 3 — то же, плюс беспроводные наушники-капли.
- Сцены 4, 11 и лифт в сцене 5 — костюм без пальто.
- Сцена 7 — белая рубашка, синий галстук.
- Сцена 12 — белая рубашка с закатанными рукавами, поверх — жилетка хаки Гены, без пальто. В руке жёлтая губка.

**Выражения для генерации:** скепсис; сухая полуулыбка; шок; усталое смирение.

---

## Вера — брокер, 44 года

**В кадре:** спокойная, почти не двигается, когда говорит. Смотрит прямо, никогда не повышает голос.

**Описание `{VERA}`:**

```
Vera, a 44-year-old Russian woman with dark hair in a low bun and calm, sharp eyes, wearing a charcoal grey trouser suit, a black puffer jacket, a mustard-yellow scarf and white sneakers
```

**Костюм по сценам:**
- На улице (сцены 2, 6, 8–10) — как в описании.
- В помещении (сцены 4, 11) — без пуховика, шарф на шее. В запросе заменить `a black puffer jacket, ` на пустое место.

**Реквизит:** стальной термос, потёртый коричневый кожаный блокнот, телефон, толстая папка накладных (сцена 6).

**Выражения для генерации:** спокойное внимание; едва приподнятая бровь; короткий кивок.

---

## Галина Петровна — председатель совета дома, 71 год

**В кадре:** прямая осанка, медленные точные жесты. Говорит, не повышая голоса, и почти не моргает.

**Описание `{PETROVNA}`:**

```
Galina Petrovna, a 71-year-old Russian woman with an upright posture and a stern, calm face, wearing a burgundy beret, a camel wool coat, reading glasses on a chain and red lipstick
```

**Костюм:** одинаковый во всех сценах, в том числе у окна в сцене 7 — она собирается выйти к шлагбауму.

**Реквизит:** брелок с котиком, ведро и губка (сцена 5), смартфон, крышка термоса с чаем (сцена 10).

**Выражения для генерации:** каменное спокойствие; оценивающий взгляд поверх очков; тень обиды; едва заметное удовлетворение.

---

## Реквизит

Каждый предмет из списка ниже генерируется отдельной картинкой-референсом:

```
product reference photo of {ITEM}: three-quarter front view and side view, neutral light grey background, even soft light, photorealistic, no text
```

| Ключ | Что это | Описание для запроса |
|---|---|---|
| `{VOLGA_CLEAN}` | Чистая «Волга» — главная деталь фильма | `a spotless glossy black 1970s Soviet GAZ-24 Volga sedan, boxy body, chrome grille with vertical bars, round headlights, chrome bumpers and chrome hubcaps` |
| `{VOLGA_DIRTY}` | Та же «Волга», грязная. Делать из картинки чистой (тот же ракурс), а не с нуля | `the same black GAZ-24 Volga sedan covered in dried grey road slush and dust, dull and filthy, rear window caked with dust` |
| `{BARRIER}` | Шлагбаум с будкой | `a red-and-white striped parking barrier arm on a grey motorized post beside a small white guard booth` |
| `{FOB_PETROVNA}` | Брелок Петровны | `a small grey plastic remote fob with a tiny worn grey plush cat keychain` |
| `{FOB_GENA}` | Брелок Гены | `a black remote fob with a red button on a heavy ring of old keys` |
| `{NIVA}` | Машина Гены | `an old dark-green Lada Niva 4x4 with mud-splattered doors` |
| `{CARSHARE}` | Каршеринг Артёма | `a plain white compact sedan with no logos or stickers` |
| `{CLICKER}` | Кликер Артёма | `a chrome mechanical hand tally counter` |

Предметы без отдельного референса: синие 20-литровые канистры, стальной термос, ярко-жёлтая губка для мойки, картонная коробка, чёрно-белое фото в рамке (мужчина в кепке у чёрной «Волги»).

**Важно про «Волгу».** Чистая и грязная «Волга» должны быть одной и той же машиной. Сначала утвердить `{VOLGA_CLEAN}`, потом получить `{VOLGA_DIRTY}` редактированием той же картинки. Во всех кадрах «Волга» стоит на одном месте у подъезда (см. `locations.md`).
