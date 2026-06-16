from PIL import Image, ImageDraw, ImageFont
import textwrap
import os

W, H = 800, 480
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (160, 160, 160)

PANEL_SPLIT = 390
HEADER_H = 72
LINESCORE_Y = 372

FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def _font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    path = os.path.join(FONT_DIR, name)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


# Pre-load fonts
F48B = _font(48, bold=True)
F28B = _font(28, bold=True)
F20B = _font(20, bold=True)
F18B = _font(18, bold=True)
F16  = _font(16)
F14  = _font(14)
F13  = _font(13)
F12  = _font(12)
F11  = _font(11)


def _text(draw, xy, text, font, fill=WHITE, anchor="la"):
    draw.text(xy, str(text), font=font, fill=fill, anchor=anchor)


def _hline(draw, y, x0=0, x1=W, fill=WHITE, width=1):
    draw.line([(x0, y), (x1, y)], fill=fill, width=width)


def _vline(draw, x, y0=HEADER_H, y1=LINESCORE_Y, fill=WHITE, width=1):
    draw.line([(x, y0), (x, y1)], fill=fill, width=width)


def render_image(data):
    img = Image.new("RGB", (W, H), BLACK)
    draw = ImageDraw.Draw(img)

    status = data.get("status", "")

    if status == "off_day":
        _render_offday(draw, data)
    elif status == "Preview":
        _render_pregame(draw, data)
    elif status == "Live":
        _render_live(draw, data)
    elif status == "Final":
        _render_final(draw, data)
    else:
        _render_error(draw, data)

    return img


def _render_header(draw, data, status_label):
    away = data["away"]
    home = data["home"]
    away_score = data.get("away_score", 0)
    home_score = data.get("home_score", 0)

    # Team abbreviations
    _text(draw, (15, 8), away["abbr"], F28B)
    _text(draw, (W - 15, 8), home["abbr"], F28B, anchor="ra")

    # Score
    score_str = f"{away_score}  –  {home_score}"
    _text(draw, (W // 2, 5), score_str, F48B, anchor="ma")

    # Records + inning/status row
    _text(draw, (15, 52), away["record"], F13)
    _text(draw, (W - 15, 52), home["record"], F13, anchor="ra")
    _text(draw, (W // 2, 52), status_label, F14, anchor="ma")

    _hline(draw, HEADER_H - 1)


def _inning_label(data):
    half = data.get("inning_half", "Top")
    inn = data.get("inning", 1)
    outs = data.get("outs", 0)
    return f"{half} {inn}  ·  {outs} Out{'s' if outs != 1 else ''}"


def _render_live(draw, data):
    label = _inning_label(data) + "   ◉ LIVE"
    _render_header(draw, data, label)

    _vline(draw, PANEL_SPLIT)

    _render_left_live(draw, data)
    _render_right_live(draw, data)
    _render_linescore(draw, data)


def _render_left_live(draw, data):
    x = 15
    pitcher = data.get("pitcher", {})
    batter = data.get("batter", {})

    # --- PITCHER ---
    _text(draw, (x, HEADER_H + 6), "PITCHER", F11, fill=GRAY)
    _text(draw, (x, HEADER_H + 20), pitcher.get("name", ""), F18B)
    pc = pitcher.get("pitch_count", 0)
    ks = pitcher.get("strikes", 0)
    era = pitcher.get("era", "N/A")
    _text(draw, (x, HEADER_H + 44), f"ERA {era}   ·   {pc} pitches / {ks} strikes", F13)

    _hline(draw, HEADER_H + 72, x0=0, x1=PANEL_SPLIT)

    # --- BATTER ---
    by = HEADER_H + 78
    _text(draw, (x, by), "AT BAT", F11, fill=GRAY)
    name = batter.get("name", "")
    pos = batter.get("lineup_pos", "")
    _text(draw, (x, by + 14), f"{name}  ({pos})", F18B)
    avg = batter.get("avg", ".---")
    hr = batter.get("hr", 0)
    rbi = batter.get("rbi", 0)
    _text(draw, (x, by + 38), f"{avg}  ·  {hr} HR  ·  {rbi} RBI", F13)
    bvp_h = batter.get("bvp_h", 0)
    bvp_ab = batter.get("bvp_ab", 0)
    bvp_hr = batter.get("bvp_hr", 0)
    bvp_k = batter.get("bvp_k", 0)
    _text(draw, (x, by + 56), f"vs pitcher:  {bvp_h}-{bvp_ab}  ·  {bvp_hr} HR  ·  {bvp_k} K", F13, fill=GRAY)

    _hline(draw, HEADER_H + 156, x0=0, x1=PANEL_SPLIT)

    # --- BSO ---
    bso_y = HEADER_H + 168
    balls = data.get("balls", 0)
    strikes = data.get("strikes", 0)
    outs = data.get("outs", 0)
    _draw_bso(draw, x, bso_y, balls, strikes, outs)


def _draw_bso(draw, x, y, balls, strikes, outs):
    dot_r = 7
    gap = 20
    label_x = x
    dot_start = x + 28

    rows = [("B", 4, balls), ("S", 3, strikes), ("O", 3, outs)]
    for i, (label, total, filled) in enumerate(rows):
        row_y = y + i * 32
        _text(draw, (label_x, row_y), label, F16)
        for j in range(total):
            cx = dot_start + j * gap
            cy = row_y + 8
            bbox = [cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r]
            if j < filled:
                draw.ellipse(bbox, fill=WHITE)
            else:
                draw.ellipse(bbox, outline=WHITE, width=2)


def _render_right_live(draw, data):
    x = PANEL_SPLIT + 15
    last_pitch = data.get("last_pitch", {})
    last_play = data.get("last_play", "")

    # --- LAST PITCH ---
    _text(draw, (x, HEADER_H + 6), "LAST PITCH", F11, fill=GRAY)
    pitch_type = last_pitch.get("type", "—")
    speed = last_pitch.get("speed")
    speed_str = f"  {speed} mph" if speed else ""
    _text(draw, (x, HEADER_H + 20), f"{pitch_type}{speed_str}", F18B)
    _text(draw, (x, HEADER_H + 44), last_pitch.get("description", ""), F14)

    _hline(draw, HEADER_H + 72, x0=PANEL_SPLIT, x1=W)

    # --- LAST PLAY ---
    lp_y = HEADER_H + 78
    _text(draw, (x, lp_y), "LAST PLAY", F11, fill=GRAY)
    lines = textwrap.wrap(last_play, width=32)
    for i, line in enumerate(lines[:3]):
        _text(draw, (x, lp_y + 14 + i * 18), line, F14)

    _hline(draw, HEADER_H + 156, x0=PANEL_SPLIT, x1=W)

    # --- DIAMOND ---
    bases = data.get("bases", {})
    diamond_cx = PANEL_SPLIT + (W - PANEL_SPLIT) // 2
    diamond_cy = HEADER_H + 156 + (LINESCORE_Y - (HEADER_H + 156)) // 2
    _draw_diamond(draw, diamond_cx, diamond_cy, 58, bases)


def _draw_diamond(draw, cx, cy, size, bases):
    top    = (cx,        cy - size)  # 2nd
    right  = (cx + size, cy)         # 1st
    bottom = (cx,        cy + size)  # home
    left   = (cx - size, cy)         # 3rd

    draw.line([top, right, bottom, left, top], fill=WHITE, width=2)

    dot_r = 9
    base_map = {"second": top, "first": right, "third": left}

    for base_name, pos in base_map.items():
        runner = bases.get(base_name)
        bbox = [pos[0] - dot_r, pos[1] - dot_r, pos[0] + dot_r, pos[1] + dot_r]
        if runner:
            draw.ellipse(bbox, fill=WHITE)
        else:
            draw.ellipse(bbox, outline=WHITE, width=2)

    # Home plate (always empty outline)
    hp_r = 6
    draw.ellipse(
        [bottom[0] - hp_r, bottom[1] - hp_r, bottom[0] + hp_r, bottom[1] + hp_r],
        outline=WHITE, width=2,
    )

    # Runner name labels
    label_font = F11
    for base_name, pos in base_map.items():
        runner = bases.get(base_name)
        if runner:
            last_name = runner.split()[-1] if runner else ""
            if base_name == "second":
                _text(draw, (pos[0], pos[1] - dot_r - 14), last_name, label_font, anchor="ma")
            elif base_name == "first":
                _text(draw, (pos[0] + dot_r + 4, pos[1]), last_name, label_font, anchor="lm")
            elif base_name == "third":
                _text(draw, (pos[0] - dot_r - 4, pos[1]), last_name, label_font, anchor="rm")


def _render_linescore(draw, data):
    grid = data.get("linescore_grid", {})
    away_abbr = data["away"]["abbr"]
    home_abbr = data["home"]["abbr"]

    y_top = LINESCORE_Y
    _hline(draw, y_top)

    team_col = 10
    col0 = 68       # first inning column
    col_w = 38
    r_x = col0 + 9 * col_w + 6
    h_x = r_x + 44
    e_x = h_x + 40
    lob_x = e_x + 40

    header_y = y_top + 5
    _text(draw, (team_col, header_y), "", F11, fill=GRAY)
    for i in range(9):
        _text(draw, (col0 + i * col_w + col_w // 2, header_y), str(i + 1), F11, fill=GRAY, anchor="ma")
    _text(draw, (r_x + 18, header_y), "R", F11, fill=GRAY, anchor="ma")
    _text(draw, (h_x + 18, header_y), "H", F11, fill=GRAY, anchor="ma")
    _text(draw, (e_x + 18, header_y), "E", F11, fill=GRAY, anchor="ma")
    _text(draw, (lob_x + 22, header_y), "LOB", F11, fill=GRAY, anchor="ma")

    for row_idx, (abbr, side) in enumerate([(away_abbr, "away"), (home_abbr, "home")]):
        row_y = y_top + 24 + row_idx * 28
        side_data = grid.get(side, {})
        innings = side_data.get("innings", [""] * 9)

        _text(draw, (team_col, row_y), abbr, F13, anchor="la")
        for i, val in enumerate(innings[:9]):
            _text(draw, (col0 + i * col_w + col_w // 2, row_y), val or "-", F13, anchor="ma")

        _text(draw, (r_x + 18, row_y), str(side_data.get("r", 0)), F13, anchor="ma")
        _text(draw, (h_x + 18, row_y), str(side_data.get("h", 0)), F13, anchor="ma")
        _text(draw, (e_x + 18, row_y), str(side_data.get("e", 0)), F13, anchor="ma")
        lob = side_data.get("lob", "")
        _text(draw, (lob_x + 22, row_y), str(lob) if lob != "" else "-", F13, anchor="ma")


def _render_pregame(draw, data):
    start = data.get("start_time", "")
    label = f"First Pitch {start}" if start else "Preview"
    _render_header(draw, data, label)
    _hline(draw, HEADER_H + 1)

    cx = W // 2
    my = (HEADER_H + LINESCORE_Y) // 2

    _text(draw, (cx, my - 60), "PROBABLE PITCHERS", F14, fill=GRAY, anchor="ma")
    _hline(draw, my - 42, x0=cx - 150, x1=cx + 150, fill=GRAY)

    away = data.get("away_probable", {})
    home = data.get("home_probable", {})

    _text(draw, (cx // 2, my - 20), data["away"]["abbr"], F20B, anchor="ma")
    _text(draw, (cx // 2, my + 8), away.get("name", "TBD"), F16, anchor="ma")
    _text(draw, (cx // 2, my + 30), f"ERA {away.get('era', 'N/A')}", F14, fill=GRAY, anchor="ma")

    _text(draw, (cx + cx // 2, my - 20), data["home"]["abbr"], F20B, anchor="ma")
    _text(draw, (cx + cx // 2, my + 8), home.get("name", "TBD"), F16, anchor="ma")
    _text(draw, (cx + cx // 2, my + 30), f"ERA {home.get('era', 'N/A')}", F14, fill=GRAY, anchor="ma")

    _text(draw, (cx, my + 10), "vs", F20B, anchor="ma")

    weather = data.get("weather", "")
    if weather:
        _text(draw, (cx, my + 68), weather, F13, fill=GRAY, anchor="ma")

    _render_linescore(draw, data)


def _render_final(draw, data):
    outs = data.get("inning", 9)
    label = f"Final  ·  {outs} innings" if outs != 9 else "Final"
    _render_header(draw, data, label)

    x = 30
    y = HEADER_H + 18

    winner = data.get("winner")
    loser = data.get("loser")
    save = data.get("save")

    if winner:
        _text(draw, (x, y), "W", F18B, fill=WHITE)
        _text(draw, (x + 32, y), f"{winner['name']}", F16)
        _text(draw, (x + 32, y + 20), f"{winner['record']}  ERA {winner['era']}", F13, fill=GRAY)
    if loser:
        y2 = y + 55
        _text(draw, (x, y2), "L", F18B, fill=WHITE)
        _text(draw, (x + 32, y2), f"{loser['name']}", F16)
        _text(draw, (x + 32, y2 + 20), f"{loser['record']}  ERA {loser['era']}", F13, fill=GRAY)
    if save:
        y3 = y + 110
        _text(draw, (x, y3), "S", F18B, fill=WHITE)
        _text(draw, (x + 32, y3), f"{save['name']}", F16)
        _text(draw, (x + 32, y3 + 20), f"{save['saves']} SV  ERA {save['era']}", F13, fill=GRAY)

    dur = data.get("duration", "")
    att = data.get("attendance", "")
    details = "  ·  ".join(filter(None, [f"Time: {dur}" if dur else "", f"Att: {att}" if att else ""]))
    if details:
        _text(draw, (W // 2, LINESCORE_Y - 18), details, F13, fill=GRAY, anchor="ma")

    _render_linescore(draw, data)


def _render_offday(draw, data):
    img_draw = draw
    _text(draw, (W // 2, H // 2 - 20), "No Game Today", F28B, anchor="ma")
    away = data.get("away", {})
    home = data.get("home", {})


def _render_error(draw, data):
    msg = data.get("message", "Unknown error")
    _text(draw, (W // 2, H // 2 - 16), "Error loading game data", F18B, anchor="ma")
    _text(draw, (W // 2, H // 2 + 16), msg[:80], F14, fill=GRAY, anchor="ma")
