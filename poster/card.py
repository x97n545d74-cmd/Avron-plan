"""AVRON news card (bright & clean). Text on the card is copied from the item's own headline/detail; nothing is added or reworded.
No source is shown on the card (user rule: never mention where the information came from)."""
import re, textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1600, 900
F = '/usr/share/fonts/opentype/inter/'
def font(name, size): return ImageFont.truetype(F + name + '.otf', size)
INK, MUTED, CANVAS = (11, 18, 32), (98, 108, 128), (245, 246, 250)
STOPS = [(79, 70, 229), (139, 92, 246), (6, 182, 212), (244, 114, 94)]  # indigo, violet, cyan, coral

HERO = [
    r'(?:₹|INR|RS\.?)\s?[\d,]+(?:\.\d+)?\s?(?:CRORE|MILLION|BILLION|LAKH)?',
    r'NIFTY 50 (?:UP|DOWN) [\d.]+%',
    r'(?:(?:UP|DOWN|FALLS?|RISES?|SHEDS?|GAINS?|DROPS?|SURGES?|JUMPS?|SLIDES?|TUMBLES?|ENDS?)\s+)?[\d.]+%\s+(?:LOWER|HIGHER)',
    r'(?:UP|DOWN|FALLS?|RISES?|SHEDS?|GAINS?|DROPS?|SURGES?|JUMPS?|SLIDES?|TUMBLES?)\s+(?:(?:NEARLY|ABOUT|OVER|AROUND|ALMOST)\s+)?[\d.]+%',
    r'[\d,]+(?:\.\d+)? ?MW',
]
LANE = {'filing': 'COMPANY FILING', 'nse': 'EXCHANGE FILING', 'news': 'MARKET NEWS', 'radar': 'MARKET CLOSE', 'story': 'STORY', 'deals': 'DEALS', 'targets': 'TARGETS'}

def hero_of(headline):
    body = headline.split(':', 1)[-1]
    if re.search(r'\b(UP|GAINS?|RISES?|HIGHER|JUMPS?|SURGES?)\b',body,re.I) and re.search(r'\b(DOWN|FALLS?|DROPS?|LOWER|SLIDES?|TUMBLES?|SHEDS?)\b',body,re.I): return None
    best = None
    for pat in HERO:
        m = re.search(pat, body, re.I)
        if m and (best is None or m.start() < best.start()): best = m
    return best.group(0).strip(' ,.') if best else None

def gradient_text(img, xy, text, fnt):
    d = ImageDraw.Draw(img)
    l, t, r, b = d.textbbox(xy, text, font=fnt)
    mask = Image.new('L', img.size, 0); ImageDraw.Draw(mask).text(xy, text, font=fnt, fill=255)
    grad = Image.new('RGB', img.size)
    gd = ImageDraw.Draw(grad)
    span = max(r - l, 1)
    for x in range(l, r + 1):
        t_ = (x - l) / span * (len(STOPS) - 1); i = min(int(t_), len(STOPS) - 2); f = t_ - i
        c = tuple(int(STOPS[i][k] + (STOPS[i + 1][k] - STOPS[i][k]) * f) for k in range(3))
        gd.line([(x, t - 4), (x, b + 4)], fill=c)
    img.paste(grad, (0, 0), mask)
    return r - l

def fit(draw, text, name, start, maxw, minsize=44):
    s = start
    while s > minsize and draw.textlength(text, font=font(name, s)) > maxw: s -= 4
    return font(name, s)

def render(item, out):
    head = item['headline']; company, _, rest = head.partition(':')
    rest = rest.strip() or head
    hero = hero_of(head)
    img = Image.new('RGB', (W, H), CANVAS)
    # slow colour fields
    fields = Image.new('RGB', (W, H), CANVAS); fd = ImageDraw.Draw(fields)
    for (cx, cy, r, c) in [(130, 120, 520, STOPS[0]), (1500, 140, 460, STOPS[2]), (1380, 820, 520, STOPS[3]), (120, 840, 380, STOPS[1])]:
        fd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
    fields = fields.filter(ImageFilter.GaussianBlur(190))
    img = Image.blend(img, fields, 0.30)
    # white product card with layered soft shadow
    cx0, cy0, cx1, cy1 = 90, 90, W - 90, H - 90
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle([cx0, cy0 + 26, cx1, cy1 + 26], 44, fill=(11, 18, 32, 40))
    img.paste(Image.new('RGB', (W, H), (11, 18, 32)), (0, 0), sh.filter(ImageFilter.GaussianBlur(34)).split()[3])
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([cx0, cy0, cx1, cy1], 44, fill=(255, 255, 255), outline=(228, 231, 240), width=2)
    px = cx0 + 80; maxw = cx1 - cx0 - 160
    # chip row
    chip = LANE.get(item.get('lane'), 'MARKET NEWS')
    cf = font('Inter-SemiBold', 26)
    tw = d.textlength(chip, font=cf)
    d.rounded_rectangle([px, cy0 + 70, px + tw + 56, cy0 + 70 + 56], 28, fill=(238, 240, 252))
    d.ellipse([px + 20, cy0 + 70 + 22, px + 32, cy0 + 70 + 34], fill=STOPS[0])
    d.text((px + 42, cy0 + 70 + 12), chip, font=cf, fill=STOPS[0])
    # company
    y = cy0 + 150
    d.text((px, y), company.strip(), font=fit(d, company.strip(), 'InterDisplay-Bold', 74, maxw, 48), fill=INK)
    y += 100
    if hero:
        hf = fit(d, hero, 'InterDisplay-ExtraBold', 200, maxw, 90)
        gradient_text(img, (px, y), hero, hf); d = ImageDraw.Draw(img)
        y += hf.size + 40
    # headline remainder, verbatim, wrapped
    body = rest if len(rest) <= 150 else rest[:147].rsplit(' ', 1)[0] + '...'
    bf = font('InterDisplay-Medium', 40 if hero else 52)
    avg = d.textlength('abcdefghij klmnopqrst', font=bf) / 21
    for ln in textwrap.wrap(body, width=max(int(maxw * 0.88 / avg), 20))[: 3 if hero else 5]:
        d.text((px, y), ln, font=bf, fill=MUTED if hero else INK); y += bf.size + 14
    # footer wordmark
    wf = font('InterDisplay-Bold', 40)
    d.text((px, cy1 - 62), 'AVRON', font=wf, fill=INK)
    d.ellipse([px + d.textlength('AVRON', font=wf) + 10, cy1 - 62 + 22, px + d.textlength('AVRON', font=wf) + 26, cy1 - 62 + 38], fill=STOPS[3])
    img.save(out, 'PNG', optimize=True)
    return out

if __name__ == '__main__':
    import json, sys
    D = 'avron-x-merger/'
    rows = [json.loads(l) for l in open(D + 'queue.jsonl')] + [json.loads(l) for l in open(D + 'radar.jsonl')]
    by = {r['id']: r for r in rows}
    for i in sys.argv[2:]: print(render(by[i], f'{sys.argv[1]}/card_{i}.png'))
