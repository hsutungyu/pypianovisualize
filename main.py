import pygame.midi
import sys
import pygame.midi
from PyQt5 import QtWidgets, QtCore
import func
from Label import Ui_MainWindow
import ntpath
import librosa
import sounddevice as sd

import time

# import pychord......

# TODO: visualizer color depends on the 'mood' of the chords
# TODO: even pure sine wave can be great
# TODO: movement of visualization independent of height (CANNOT)
# TODO: change MIDI read function, loop through list instead of assuming only one at a time
# TODO: sine wave generator, chromagram to note --> pass to chord
# TODO: play audio and sync with note visualization (middle C's octave)

# list for storing the MIDI number of black keys, for changing the background color
BLACKKEYMIDI = [34, 37, 39, 42, 44, 46, 49, 51, 54, 56, 58, 61, 63, 66, 68, 70, 73, 75, 78, 80, 82, 85, 87, 90, 92, 94,
                97, 99, 102, 104, 106, 109, 111, 114, 116, 118]
# list for storing all possible MIDI numbers
MIDI = []
for i in range(33, 121):
    MIDI.append(i)
# constant for setting update ticks (in ms)
TICK = 17  # 60FPS = 1 / 60 * 1000 ~ 17
# constant for time threshold of note input
THRESHOLD = 50

# use pygame.midi to play the chord
# use pygame to continuously receive input from MIDI keyboard
pygame.init()
pygame.fastevent.init()
event_get = pygame.fastevent.get
event_post = pygame.fastevent.post
pygame.midi.init()
midiinput = pygame.midi.Input(1)
player = pygame.midi.Output(0)
player.set_instrument(0)


# Thread for monitoring MIDI input
class MIDIThread(QtCore.QThread):
    # trigger for outputting the chord name to the GUI
    triggerName = QtCore.pyqtSignal(str)
    # trigger for highlighting notes played on GUI
    triggerShowNote = QtCore.pyqtSignal(list)
    # trigger for reverting the background color change
    triggerCancelNote = QtCore.pyqtSignal(list)
    # trigger for creating moving visualization
    triggerVisual = QtCore.pyqtSignal(list, int, bool)
    # list for storing MIDI value of chord note, used by func.py
    noteMIDI = []
    # list for transmitting MIDI values to GUI
    noteGUI = []
    # number of chord notes in each chord
    count = 0
    # int for counting the time elapsed after pressing keys for visualization
    timeCount = 0
    # bool for noticing the main window if released keys
    releasedKeys = True
    # int for storing the time of the first note of each chord by accessing midi_events[0][1]
    timeFirst = 0

    def receiveMIDI(self):
        if midiinput.poll():
            midi_events = midiinput.read(10)
            # if noteMIDI is empty, i.e., first note, then set time of first note
            for x in midi_events:
                if x[0][2] != 0:
                    if not self.noteMIDI:
                        self.timeFirst = x[1]
                        self.noteGUI.append(x[0][1])
                        self.noteMIDI.append(x[0][1])
                        player.note_on(x[0][1], x[0][2])
                        self.count += 1
                        self.triggerShowNote.emit(self.noteGUI)
                        self.triggerName.emit(func.full_chord(self.noteMIDI))
                    # else if not empty, then check if input is within threshold
                    # otherwise just ignore
                    elif x[1] - THRESHOLD < self.timeFirst:
                        self.noteGUI.append(x[0][1])
                        self.noteMIDI.append(x[0][1])
                        player.note_on(x[0][1], x[0][2])
                        self.count += 1
                        self.triggerShowNote.emit(self.noteGUI)
                        self.triggerName.emit(func.full_chord(self.noteMIDI))
                # if midi_events[0][0][2] != 0:
                #     self.noteGUI.append(midi_events[0][0][1])
                #     self.noteMIDI.append(midi_events[0][0][1])
                #     player.note_on(midi_events[0][0][1], midi_events[0][0][2])
                #     self.count += 1
                #     self.triggerShowNote.emit(self.noteGUI)
                #     self.triggerName.emit(func.full_chord(self.noteMIDI))
                else:  # velocity = 0 means the user released the key, cancel highlight at this moment
                    if self.count == len(self.noteGUI):
                        self.count -= 1
                        for y in self.noteMIDI:
                            player.note_off(y, 0)
                        self.triggerCancelNote.emit(self.noteGUI)
                        # self.triggerName.emit(func.full_chord(self.noteMIDI))
                    elif self.count != 1:
                        self.count -= 1
                    else:
                        self.noteMIDI = []
                        self.noteGUI = []
                        self.count = 0
                        self.timeFirst = 0

    def visualMIDI(self):
        if self.noteMIDI:
            self.releasedKeys = False
            self.timeCount += 0.017
            self.triggerVisual.emit(self.noteGUI, self.timeCount, self.releasedKeys)
        else:
            self.releasedKeys = True
            self.timeCount = 0
            self.triggerVisual.emit(self.noteGUI, self.timeCount, self.releasedKeys)

    def __init__(self):
        QtCore.QThread.__init__(self)
        self.stopMIDI = True
        self.MIDITimer = QtCore.QTimer()
        self.MIDITimer.moveToThread(self)
        self.MIDITimer.timeout.connect(self.receiveMIDI)
        self.VisualTimer = QtCore.QTimer()
        self.VisualTimer.moveToThread(self)
        self.VisualTimer.timeout.connect(self.visualMIDI)

    def run(self):
        self.MIDITimer.start(0)
        self.VisualTimer.start(TICK)
        loop = QtCore.QEventLoop()
        loop.exec_()


# GUI initialization
class MainWindow(QtWidgets.QMainWindow):
    # list of list for storing visualization(s) that are currently on screen
    noteOnScreen = []
    # list for storing the height of visualizations that are currently on screen
    visualHeight = []
    # string for storing the file path
    filePath = ""
    # trigger for visualizing the chord detected on the keyboard
    triggerAudioVisual = QtCore.pyqtSignal(list)
    triggerAudioCancelVisual = QtCore.pyqtSignal(list)

    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        # initialize timer
        self.timer = QtCore.QTimer()
        self.timer.start(0)
        # initialize thread
        self.workThread = MIDIThread()
        self.workThread.start()
        # initialize trigger
        self.workThread.triggerName.connect(self.displayChordName)
        self.workThread.triggerShowNote.connect(self.displayNote)
        self.workThread.triggerCancelNote.connect(self.cancelNote)
        self.workThread.triggerVisual.connect(self.visualNote)
        self.triggerAudioVisual.connect(self.displayNote)
        self.triggerAudioCancelVisual.connect(self.cancelNote)
        self.scene = QtWidgets.QGraphicsScene()
        # connect button to reset function
        self.ui.resetButton.clicked.connect(self.resetChord)
        # connect button to audio file input
        self.ui.audioSelect.clicked.connect(self.audioInput)
        # connect button to audio playback and chord analyzer
        self.ui.audioPlay.clicked.connect(self.audioAnalyze)
        # initialize buttons for visualization like those fancy YouTube videos
        # template from PyUIC:
        # self.MIDI107 = QtWidgets.QPushButton(self.centralwidget)
        # self.MIDI107.setGeometry(QtCore.QRect(1289, 330, 31, 91))
        # self.MIDI107.setStyleSheet("QPushButton {background-color: white} QPushButton::pressed {background-color: red}")
        # self.MIDI107.setText("")
        # self.MIDI107.setObjectName("MIDI107")
        for i in range(33, 121):
            # find the parent of this visualization
            parentName = "MIDI" + str(i)
            srcParentObjectXCenter = "self.ui.{}.mapToParent(self.ui.{}.rect().center()).x()".format(parentName,
                                                                                                     parentName)
            srcParentObjectY = " self.ui.{}.y()".format(parentName)
            parentXCenter = eval(srcParentObjectXCenter)
            parentY = eval(srcParentObjectY)
            # create buttons for visualization
            src1 = "self.visual{} = QtWidgets.QPushButton(self)".format(i)
            src2 = "self.visual{}.setGeometry(QtCore.QRect({},{},12,0))".format(i, parentXCenter - 6, parentY - 330)
            StyleSheet = "QPushButton {background-color: red}"
            src3 = "self.visual{}.setStyleSheet('{}')".format(i, StyleSheet)
            src4 = "self.visual{}.setText('')".format(i)
            # set invisible so that proxy can be used for visualization
            src5 = "self.visual{}.setVisible(False)".format(i)
            src6 = "self.ui.{}.setVisible(False)".format(parentName)
            exec(src1)
            exec(src2)
            exec(src3)
            exec(src4)
            exec(src5)
            exec(src6)
            # putting each button inside a proxy
            src5 = "self.proxyVisual{} = self.scene.addWidget(self.visual{})".format(i, i)
            src6 = "self.proxyMIDI{} = self.scene.addWidget(self.ui.MIDI{})".format(i, i)
            # set geometry of proxies
            src7 = "self.proxyVisual{}.setGeometry(QtCore.QRectF(self.visual{}.geometry()))".format(i, i)
            src8 = "self.proxyMIDI{}.setGeometry(QtCore.QRectF(self.ui.MIDI{}.geometry()))".format(i, i)
            # set visible again after assigning into proxy
            src9 = "self.visual{}.setVisible(True)".format(i)
            src10 = "self.ui.{}.setVisible(True)".format(parentName)
            exec(src5)
            exec(src6)
            exec(src7)
            exec(src8)
            exec(src9)
            exec(src10)
        view = QtWidgets.QGraphicsView(self.scene)
        view.show()

    def audioInput(self):
        # https://www.tutorialspoint.com/pyqt/pyqt_qfiledialog_widget.htm
        fname = QtWidgets.QFileDialog.getOpenFileName(self, 'Select Audio File',
                                                      filter="Audio Files (*.mp3 *.aiff *.ogg *.wav)")
        self.filePath = fname[0]
        self.ui.audioName.setText(ntpath.basename(fname[0]))

    def resetChord(self):
        self.noteOnScreen = []
        self.noteMIDI = []
        self.noteGUI = []
        self.cancelNote(MIDI)

    def displayChordName(self, str):
        self.ui.label.setText(str)

    def displayNote(self, note):
        for x in note:
            objectName = "MIDI" + str(x)
            buttonPressedStyle = '"QPushButton {background-color: red}"'
            src = "self.ui.{}.setStyleSheet({})".format(objectName, buttonPressedStyle)
            exec(src)

    def cancelNote(self, note):
        for x in note:
            objectName = "MIDI" + str(x)
            buttonWhiteDepressedStyle = '"QPushButton {background-color: white}"'
            buttonBlackDepressedStyle = '"QPushButton {background-color: black}"'
            if x in BLACKKEYMIDI:
                src = "self.ui.{}.setStyleSheet({})".format(objectName, buttonBlackDepressedStyle)
                exec(src)
            else:
                src = "self.ui.{}.setStyleSheet({})".format(objectName, buttonWhiteDepressedStyle)
                exec(src)

    def visualNote(self, note, timeChange, releasedKeys):
        if note:
            # append to list if not already in list and if the note is playing
            if note not in self.noteOnScreen and not releasedKeys:
                for x in self.noteOnScreen:
                    print(func.checkSublist(x, note))
                    if func.checkSublist(x, note):
                        self.noteOnScreen.remove(x)
                if len(note) >= 3:
                    self.noteOnScreen.append(note)
            #     # already in list
            #     for x in self.noteOnScreen:
            #         # possibility one: the notes are being pressed down --> continue the strip
            #         if note == x:
            #             for y in x:
            #                 src = "self.visual{}.resize(12,{})".format(y, 10 * timeChange)
            #                 exec(src)
            #         # possibility two: notes have been released --> move down until disappear
            #         else:
            #             # find position of visualization on screen
            #             src1 = "self.visual{}.pos().x()".format(x)
            #             src2 = "self.visual{}.pos().y()".format(x)
            #             visualX = eval(src1)
            #             visualY = eval(src2)
            #             src3 = "self.visual{}.move({},{})".format(x, visualX, 2 * visualY)
            #             exec(src3)
            # # else if note is in list already, it means continue the strip
            elif note in self.noteOnScreen and not releasedKeys:
                for x in note:
                    src = "visualAni{} = QtCore.QPropertyAnimation(self.visual{}, b'size')".format(x, x)
                    exec(src)
                    src = "visualAni{}.setDuration(3000)".format(x)
                    exec(src)
                    src = "visualGeo{} = self.visual{}.size()".format(x, x)
                    exec(src)
                    src = "visualAni{}.setStartValue(visualGeo{})".format(x, x)
                    exec(src)
                    src = "visualGeo{}.setHeight(300 * timeChange)".format(x)
                    exec(src)
                    src = "visualAni{}.setEndValue(visualGeo{})".format(x, x)
                    exec(src)
                    src = "visualAni{}.setTargetObject(self.visual{})".format(x, x)
                    exec(src)
                    src = "visualAni{}.start()".format(x)
                    exec(src)
                    # src = "print(visualAni{}.endValue())".format(x)
                    # exec(src)
                    # https://stackoverflow.com/questions/6952852/qpropertyanimation-doesnt-work-with-a-child-widget/6953965
                    src = "self.visualAni{} = visualAni{}".format(x, x)
                    exec(src)
                    src = "self.proxyVisual{}.setGeometry(QtCore.QRectF(self.visual{}.geometry()))".format(x, x)
                    exec(src)
                for x in self.noteOnScreen:
                    if note != x:
                        for i in range(len(x)):
                            # find position of visualization on screen
                            src1 = "self.visual{}.pos().x()".format(x[i])
                            src2 = "self.visual{}.pos().y()".format(x[i])
                            src3 = "self.visual{}.geometry().height()".format(x[i])
                            visualX = eval(src1)
                            visualY = eval(src2)
                            heightY = eval(src3)
                            # if exceed keyboard, reset the position
                            src4 = "self.proxyVisual{}.collidesWithItem(self.proxyMIDI{}, QtCore.Qt.IntersectsItemBoundingRect)".format(
                                x[i], x[i])
                            isCollided = eval(src4)
                            if isCollided:
                                src5 = "self.visual{}.move({},0)".format(x[i], visualX)
                                exec(src5)
                                src5 = "self.proxyVisual{}.setGeometry(QtCore.QRectF(self.visual{}.geometry()))".format(
                                    x[i], x[i])
                                exec(src5)
                                src6 = "self.visual{}.resize(12,0)".format(x[i])
                                exec(src6)
                                if i == len(x) - 1:
                                    self.noteOnScreen = []
                                    #self.noteOnScreen.remove(x)
                            else:
                                src = "self.visualAni{}.stop()".format(x[i])
                                exec(src)
                                src7 = "self.visual{}.move({},{})".format(x[i], visualX, visualY + heightY * 0.05)
                                exec(src7)
                                src8 = "self.proxyVisual{}.setGeometry(QtCore.QRectF(self.visual{}.geometry()))".format(
                                    x[i], x[i])
                                exec(src8)
            # else from definition of thread above, it means that the keys are released
            else:
                for i in range(len(note)):
                    # find position of visualization on screen
                    src1 = "self.visual{}.pos().x()".format(note[i])
                    src2 = "self.visual{}.pos().y()".format(note[i])
                    src3 = "self.visual{}.geometry().height()".format(note[i])
                    visualX = eval(src1)
                    visualY = eval(src2)
                    heightY = eval(src3)
                    # if exceed keyboard, reset the position
                    src4 = "self.proxyVisual{}.collidesWithItem(self.proxyMIDI{}, QtCore.Qt.IntersectsItemBoundingRect)".format(
                        note[i], note[i])
                    isCollided = eval(src4)
                    if isCollided:
                        src5 = "self.visual{}.move({},0)".format(note[i], visualX)
                        exec(src5)
                        src5 = "self.proxyVisual{}.setGeometry(QtCore.QRectF(self.visual{}.geometry()))".format(
                            note[i], note[i])
                        exec(src5)
                        src6 = "self.visual{}.resize(12,0)".format(note[i])
                        exec(src6)
                        if i == len(note) - 1:
                            self.noteOnScreen = []
                            #self.noteOnScreen.remove(note)
                    else:
                        src = "self.visualAni{}.stop()".format(note[i])
                        exec(src)
                        src7 = "self.visual{}.move({},{})".format(note[i], visualX, visualY + heightY * 0.05)
                        exec(src7)
                        src8 = "self.proxyVisual{}.setGeometry(QtCore.QRectF(self.visual{}.geometry()))".format(note[i],
                                                                                                                note[i])
                        exec(src8)

        # no key is being pressed, all should go down
        else:
            # make sure that it is not the beginning, i.e., when noteOnScreen is empty
            if self.noteOnScreen:
                # print(self.noteOnScreen)
                for x in self.noteOnScreen:
                    for y in range(len(x)):
                        # find position of visualization on screen
                        src1 = "self.visual{}.pos().x()".format(x[y])
                        src2 = "self.visual{}.pos().y()".format(x[y])
                        src3 = "self.visual{}.geometry().height()".format(x[y])
                        visualX = eval(src1)
                        visualY = eval(src2)
                        heightY = eval(src3)
                        # if exceed keyboard, reset the position
                        src4 = "self.proxyVisual{}.collidesWithItem(self.proxyMIDI{}, QtCore.Qt.IntersectsItemBoundingRect)".format(
                            x[y], x[y])
                        isCollided = eval(src4)
                        if isCollided:
                            src5 = "self.visual{}.move({},0)".format(x[y], visualX)
                            exec(src5)
                            # src = "print(self.visual{}.geometry())".format(x[y])
                            # exec(src)
                            src5 = "self.proxyVisual{}.setGeometry(QtCore.QRectF(self.visual{}.geometry()))".format(
                                x[y], x[y])
                            exec(src5)
                            src6 = "self.visual{}.resize(12,0)".format(x[y])
                            exec(src6)
                            if y == len(x) - 1:
                                self.noteOnScreen = []
                                #self.noteOnScreen.remove(x)
                        else:
                            src = "self.visualAni{}.stop()".format(x[y])
                            exec(src)
                            src7 = "self.visual{}.move({},{})".format(x[y], visualX, visualY + heightY * 0.05)
                            exec(src7)
                            src8 = "self.proxyVisual{}.setGeometry(QtCore.QRectF(self.visual{}.geometry()))".format(
                                x[y], x[y])
                            exec(src8)

    def audioAnalyze(self):
        if self.filePath:
            y, sr = librosa.load(self.filePath, sr=None)
            # duration of audio
            dur = librosa.get_duration(y, sr)
            result = func.audioAnalyze(y, sr)[0]
            # TODO: deal with multiple onsets
            # because hz_to_midi returns floats MIDI number
            midi = librosa.note_to_midi(librosa.hz_to_note(result))
            chord = func.full_chord(midi)
            self.ui.label.setText(chord)
            self.displayNote(midi)
            sd.play(y, sr)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
