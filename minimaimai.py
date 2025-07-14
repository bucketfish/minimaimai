import time
import board
import math
import busio
import terminalio
import displayio
from adafruit_display_text import label
import gc9a01
import digitalio
import keypad
import pwmio
import vectorio


displayio.release_displays()


button_pins = (
    board.GP16,
    board.GP18,
    board.GP19,
    board.GP6,
    board.GP5,
    board.GP3,
    board.GP2,
    board.GP1
)



speaker = pwmio.PWMOut(board.GP8, variable_frequency=True)


keys = keypad.Keys(button_pins, value_when_pressed=False, pull=True)


tft_clk = board.GP10 # SCL
tft_mosi= board.GP11 # SDA

tft_dc  = board.GP14
tft_cs  = board.GP13
tft_rst = board.GP9
tft_bl  = board.GP15
spi = busio.SPI(clock=tft_clk, MOSI=tft_mosi)


display_bus = displayio.FourWire(spi, command=tft_dc, chip_select=tft_cs, reset=tft_rst)
display = gc9a01.GC9A01(display_bus, width=240, height=240, backlight_pin=tft_bl, rotation=180)


# create groups for layering
background_group = displayio.Group()
notes_group = displayio.Group()
feedback_group = displayio.Group()

main = displayio.Group()
main.append(background_group)  # back layer
main.append(notes_group)       # middle layer
main.append(feedback_group)    # top layer (feedback)
display.root_group = main


# settings???
note_speed = 100 # this is the note travelling.. idk what this means.



border_color = displayio.Palette(1)
border_color[0] = 0xADD8FF

bg_color = displayio.Palette(1)
bg_color[0] = 0x000000


feedbacks = []

button_positions = {
    0: (60, 40),
    1: (30, 80),
    2: (30, 160),
    3: (60, 200),
    4: (180, 200),
    5: (210, 160),
    6: (210, 80),
    7: (180, 40)
}


def show_feedback(text, color, position=(120, 120)):
    print(text)
    fb = {}
    fb['text_area'] = label.Label(
        terminalio.FONT,
        text=text,
        color=color,
        anchor_point=(0.5, 0.5),
        anchored_position=position
    )
    fb['start_time'] = time.monotonic()
    fb['duration'] = 0.5

    fb_group = displayio.Group(scale=1)
    fb_group.append(fb['text_area'])
    fb['group'] = fb_group

    feedback_group.append(fb_group)
    feedbacks.append(fb)



def update_feedbacks():
    current_time = time.monotonic()
    expired = []
    for fb in feedbacks:
        if current_time - fb['start_time'] >= fb['duration']:
            expired.append(fb)

    for fb in expired:
        feedback_group.remove(fb['group'])
        feedbacks.remove(fb)




class Song():
    def __init__(self, name, beatmap, bpm = 60):
        self.beatmap = beatmap
        self.bpm = bpm
        self.name = name

class Note():
    def __init__(self, direction):
        self.direction = direction

        self.outer_circle = vectorio.Circle(
            pixel_shader=border_color,
            radius=25,
            x=120,
            y=120
        )

        self.inner_circle = vectorio.Circle(
            pixel_shader=bg_color,
            radius=20,   # radius = outer - border thickness
            x=120,
            y=120
        )


        #self.circle = vectorio.Circle(
        #    pixel_shader = palette,
        #    radius = 20,
        #    x = 120,
        #    y = 120
        #)

        self.sx = 120
        self.sy = 120
        self.onscreen = False

    def start_note(self):
        global notes_group
        notes_group.append(self.outer_circle)
        notes_group.append(self.inner_circle)
        self.onscreen = True

    def remove(self):
        global notes_group
        if self.onscreen:
            notes_group.remove(self.inner_circle)
            notes_group.remove(self.outer_circle)
            self.onscreen = False


    def move_note(self, delta):
        global button_positions
        long = note_speed * delta * 0.924
        short = note_speed * delta * 0.383

        movements = [
            [-short, -long],
            [-long, -short],
            [-long, short],
            [-short, long],
            [short, long],
            [long, short],
            [long, -short],
            [short, -long]
        ]

        self.sx += movements[self.direction][0]
        self.sy += movements[self.direction][1]

        self.inner_circle.x = int(self.sx)
        self.inner_circle.y = int(self.sy)
        self.outer_circle.x = int(self.sx)
        self.outer_circle.y = int(self.sy)

        if not hasattr(self, "judged"):
            if self.is_in_perfect_zone():
                if is_pressed(self.direction):
                    show_feedback("Perfect!", 0x00FF00, button_positions[self.direction])
                    self.judged = True
                    self.remove()
            elif self.is_in_hit_zone():
                if is_pressed(self.direction):
                    show_feedback("Good!", 0xFFFF00, button_positions[self.direction])
                    self.judged = True
                    self.remove()
            elif self.is_missed():
                show_feedback("Miss!", 0xFF0000, button_positions[self.direction])
                self.judged = True
                self.remove()




    def is_in_perfect_zone(self):
        cx, cy = 120, 120
        dx = self.sx - cx
        dy = self.sy - cy
        dist = math.sqrt(dx * dx + dy * dy)
        return dist >= 115 and dist <= 125


    def is_in_hit_zone(self):
        cx, cy = 120, 120
        dx = self.sx - cx
        dy = self.sy - cy
        dist = math.sqrt(dx * dx + dy * dy)
        return dist >= 100 and dist <= 140



    def is_missed(self):
        cx, cy = 120, 120
        dx = self.sx - cx
        dy = self.sy - cy
        dist = math.sqrt(dx * dx + dy * dy)
        return dist >= 140







class Tap(Note):
    def __init__(self, direction):
        super().__init__(direction)

class Hold(Note):
    def __init__(self, direction, length):
        super().__init__(direction)
        self.length = length # 1 = 1 b

class Silence(Note):
    def __init__(self):
        super().__init__(0, -1)


songs = [
    Song("Demo", [
        [Tap(0), Tap(7)],
        [],
        [Tap(1), Tap(6)],
        [],
        [Tap(2)],
        [Tap(5)],
        [Tap(3), Tap(4)],
    ], bpm=120)
]



game_time = 0
prev_monotonic = -1


held_buttons = set()
prev_held_buttons = set()








def is_pressed(key_number):
    global held_buttons, prev_held_buttons
    return key_number in held_buttons

def is_just_pressed(key_number):
    global held_buttons, prev_held_buttons
    return key_number in held_buttons and key_number not in prev_held_buttons

def is_just_released(key_number):
    global held_buttons, prev_held_buttons
    return key_number not in held_buttons and key_number in prev_held_buttons


def process_input():
    global held_buttons, prev_held_buttons
    prev_held_buttons = held_buttons

    event = keys.events.get()


    if event:
        print("button", event.key_number, end=' ')

        if event.pressed:
            held_buttons.add(event.key_number)
        elif event.released:
            held_buttons.discard(event.key_number)
        else:
            pass



    # speaker.duty_cycle = 2**14
    # speaker.frequency = int(frequencies[event.key_number])

    #for i in range(len(button_pins)):
    #    if i in held_buttons:
    #        print(f"button {i} is being held")
    #        text_area.text = f"button {i}"

    #if not held_buttons:
    #    text_area.text = f"hello world"
    #    speaker.duty_cycle = 0




    #text_group.x = 120 + int(r * math.sin(theta))
    #text_group.y = 120 + int(r * math.cos(theta))
    #theta -= 0.05
    #time.sleep(0.01)





def play_song(song):
    global game_time, monotonic, prev_monotonic


    onscreen_notes = set()

    current_beat = 0

    beat_duration = 60 / song.bpm


    while True:
        update_feedbacks()

        # calculate time
        monotonic = time.monotonic()

        delta = 0
        if prev_monotonic != -1:

            delta = monotonic - prev_monotonic
        game_time += delta


        process_input()

        prev_monotonic = monotonic



        # process music
        next_beat_time = (current_beat + 1) * beat_duration


        if game_time >= next_beat_time and current_beat < len(song.beatmap):
            print("beat")
            print(current_beat)
            current_notes = song.beatmap[current_beat]
            for note in current_notes:
                note.start_note()
                onscreen_notes.add(note)



            next_beat_time += beat_duration
            current_beat += 1


        # move notes
        for note in onscreen_notes:
            if note.onscreen == False:
                onscreen_notes.discard(note)
            else:
                note.move_note(delta)



        time.sleep(0.01)




def show_instructions():
    pages = [
        [
            "minimaimai",
            "by tongyu!",
            "",
            "press any button",
            "to begin :)"
        ],
        [
            "how to play:",
            "notes fly out from center",
            "press matching button",
            "when they reach the edge.",
            "(perfect if at center of edge!)",
            "",
            "good luck!"
        ]
    ]

    for page in pages:
        instruction_group = displayio.Group()
        for i, line in enumerate(page):
            instruction = label.Label(
                terminalio.FONT,
                text=line,
                color=0xFFFFFF,
                anchor_point=(0.5, 0.5),
                anchored_position=(120, 50 + i * 15)
            )
            instruction_group.append(instruction)

        main.append(instruction_group)

        while True:
            event = keys.events.get()
            if event and event.pressed:
                break
            time.sleep(0.01)

        main.remove(instruction_group)



while True:
    show_instructions()
    play_song(songs[0])
