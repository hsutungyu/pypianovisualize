import librosa
import numpy

# constant list NOTE: all 12 notes, sharps only for simplicity
NOTE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# constant list QUALITY: distances between chord notes uniquely determine the quality and inversion
# dominant seventh: packed, then third is root (3,2,4) --> (3, 2, 4): ["7", 2]
# major: first is root (4,3) / third is root (3,5)
# minor: first is root (3,4) / third is root (4,5)
QUALITY = {(4, 3): ["a", 0], (3, 5): ["b", 2], (5, 4): ["c", 1],
           (3, 4): ["ma", 0], (4, 5): ["mb", 2], (5, 3): ["mc", 1],
           (4, 3, 3): ["7a", 0], (3, 3, 2): ["7b", 3], (3, 2, 4): ["7c", 2], (2, 4, 3): ["7d", 1],
           (2, 2, 3, 3): ["9a", 0], (3, 3, 2, 2): ["9b", 3], (3, 2, 2, 2): ["9c", 2], (2, 2, 2, 3): ["9d", 1],
           (2, 3, 3, 2): ["9e", 4],
           (3, 3, 3): ["dim7", 0],
           (3, 3): ["dima", 0],
           (4, 4): ["+", 0],
           (2, 5): ["sus2", 0], (5, 2): ["sus4", 0],
           (4, 6): [" Italian 6th", 1]}


# function for combining note and octave, return a list of list containing string representation of notes
# input: list containing lists of notes and list containing lists of their corresponding octaves
# output: list containing string representation of notes with octaves
def full_note(note, octave):
    noteFull = []
    for i in range(len(note)):
        temp = []
        for j in range(len(note[i])):
            temp.append(NOTE[note[i][j]] + str(octave[i][j]))
        noteFull.append(temp)
    return noteFull


# function for detecting the qualities of chords
# input: a list containing notes
# output: a string of full name of chord (bass note, quality, inversion)
def full_chord(noteMIDI):
    new_noteMIDI = noteMIDI
    # sort the noteMIDI list
    new_noteMIDI.sort()
    # the lowest note is the pivot, move other note down octave(s), so that
    # all notes are within one octave from the lowest note
    for i in range(len(new_noteMIDI) - 1):
        while new_noteMIDI[i + 1] >= new_noteMIDI[0] + 12:
            new_noteMIDI[i + 1] -= 12  # 12 notes in one octave
    # now that all notes are with in one octave of each other, remove duplicate notes, then sort again
    new_noteMIDI = list(set(new_noteMIDI))
    new_noteMIDI.sort()
    # find distance between each note
    dis = []
    for i in range(len(new_noteMIDI) - 1):
        dis.append(new_noteMIDI[i + 1] - new_noteMIDI[i])
    # this gives us the quality and the inversion of the chord
    result = QUALITY.get(tuple(dis))
    if result is None:
        return "No chord is found!"
    # find the root note of the chord
    root = librosa.midi_to_note(new_noteMIDI[result[1]], octave=False)

    return root + result[0]


# function for returning unique MIDI list
def unique_MIDI(noteMIDI):
    new_noteMIDI = noteMIDI
    # remove duplicate notes
    new_noteMIDI = list(set(new_noteMIDI))

    return new_noteMIDI


def detect_pitch(p, t):
    index = numpy.nonzero(p[:, t])
    pitch = p[index, t]
    return pitch


# boolean: True if is harmonics, False if is not
def checkHarmonics(freq1, freq2):
    # freq 2 is larger
    result = freq2 / freq1
    if result.is_integer():
        return True
    else:
        return False


# TODO: this only works for pure sine wave: consider whole list, count the occurence, output the most likely chord
# return a list containing chord notes from the audio input
# https://librosa.org/doc/main/generated/librosa.piptrack.html
def audioAnalyze(y, sr):
    # librosa.piptrack to extract pitch
    pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
    # the first ~10 columns are often meaningless
    pitches_candidate = []
    for time in range(10, len(pitches[0])):
        pitches_candidate.append(detect_pitch(pitches, time))
    # onset_detection: assumption: chord usually happen just after onset
    onset_frames = librosa.onset.onset_detect(y, sr)
    chord_note_candidate = []
    for x in onset_frames:
        if x <= len(pitches_candidate):
            # so that the frequencies can be conveniently rounded to exact frequencies for excluding the harmonics
            chord_note_candidate.append(librosa.note_to_hz(librosa.hz_to_note(pitches_candidate[x])))
    chord_note_no_harmonics = []

    for x in chord_note_candidate:
        # x is a list of list (...), so x[0] corresponding to freq in an onset
        temp = []
        for i in range(0, len(x[0])):
            if i == 0:
                temp.append(x[0][i])
            for j in range(0, i):
                if j == i - 1:
                    temp.append(x[0][i])
                    break
                elif checkHarmonics(x[0][j], x[0][i]):
                    break
        chord_note_no_harmonics.append(temp)

    # https://stackoverflow.com/questions/3724551/python-uniqueness-for-list-of-lists
    chord_note_no_harmonics = [list(x) for x in set(tuple(x) for x in chord_note_no_harmonics)]

    return chord_note_no_harmonics


# check if list1 is sublist of list2
# list1: list, list2: list
# return True if list1 is sublist of list2, False if otherwise
# https://stackoverflow.com/questions/35964155/checking-if-list-is-a-sublist
def checkSublist(list1, list2):
    # if list2 is empty, immediately return False
    if not list2:
        return False
    listtest1 = [element for element in list1 if element in list2]
    listtest2 = [element for element in list2 if element in list1]
    # if list1 is sublist of x, return True
    if listtest1 == listtest2:
        return True
    else:
        return False
