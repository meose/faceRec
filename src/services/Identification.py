from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage
from scipy.ndimage.filters import gaussian_filter

import os
import json
import numpy as np

import imutils


class Identification(QtCore.QThread):
    log = pyqtSignal(str)
    up = pyqtSignal(QImage)
    process = pyqtSignal(QImage)
    allowStopIdentification = pyqtSignal()
    disAllowStopIdentification = pyqtSignal()
    successfulSaveIdentificationResult = pyqtSignal()

    def __init__(self, parent=None, face_detect=None, aligner=None, extract_feature=None, name=None, vs=None,
                 rotation=None, jsonpath=None):
        QtCore.QThread.__init__(self, parent)
        self.__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
        self.name = name
        self.aligner = aligner
        self.extract_feature = extract_feature
        self.face_detect = face_detect
        self.vs = vs
        self.jsonpath = jsonpath

        self.rotation = rotation

        self.running = False
        self.success = False

        f = open(self.jsonpath, 'r')
        self.data_set = json.loads(f.read())
        self.person_imgs = {"Left": [], "Right": [], "Center": []}
        self.person_features = {"Left": [], "Right": [], "Center": []}
        self.max_length = 50

    def run(self):
        try:
            self.running = True
            while self.running:
                _, frame = self.vs.read()
                frame = imutils.rotate_bound(frame, self.rotation)
                rects, landmarks = self.face_detect.detect_face(frame, 80)  # min face size is set to 80x80
                if len(rects) == 0:
                    image = QtGui.QImage(frame, frame.shape[1], frame.shape[0], frame.shape[1] * 3,
                                         QtGui.QImage.Format_RGB888).rgbSwapped()
                    self.up.emit(image)
                else:
                    for (i, rect) in enumerate(rects):
                        aligned_frame, pos = self.aligner.align(160, frame, landmarks[i])
                        if len(aligned_frame) == 160 and len(aligned_frame[0]) == 160:

                            if pos == "Left" and len(self.person_imgs["Left"]) <= self.max_length:
                                self.person_imgs[pos].append(aligned_frame)

                            if pos == "Right" and len(self.person_imgs["Right"]) <= self.max_length:
                                self.person_imgs[pos].append(aligned_frame)

                            if pos == "Center" and len(self.person_imgs["Center"]) <= self.max_length:
                                self.person_imgs[pos].append(aligned_frame)

                            left = len(self.person_imgs["Left"]) != 0
                            right = len(self.person_imgs["Right"]) != 0
                            center = len(self.person_imgs["Center"]) != 0

                            if not self.running:
                                frame = gaussian_filter(frame, sigma=12)

                            else:
                                frame[10:10+aligned_frame.shape[0], 10:10+aligned_frame.shape[1]] = aligned_frame

                            image = QtGui.QImage(frame, frame.shape[1], frame.shape[0], frame.shape[1] * 3, QtGui.QImage.Format_RGB888).rgbSwapped()

                            if left and right and center and self.running:
                                self.allowStopIdentification.emit()

                            if self.running:
                                self.up.emit(image)
                            elif self.success:
                                self.process.emit(image)
                                self.save()

                if not self.running:
                    self.quit()

        except Exception as e:
            print(str(e))

    @pyqtSlot(name="interrupt")
    def interrupt(self):
        self.disAllowStopIdentification.emit()
        self.running = False
        self.log.emit("Идентификация прервана по просьбе пользователя")
        print("Identification thread is killed")
        self.wait()

    @pyqtSlot(name="saveIdentificationResult")
    def stop(self):
        self.running = False
        self.success = True

    def save(self):
        try:
            self.disAllowStopIdentification.emit()
            self.running = False
            try:
                for pos in self.person_imgs:
                    self.person_features[pos] = [np.mean(self.extract_feature.get_features(self.person_imgs[pos]), axis=0).tolist()]
            except Exception as e:
                self.log.emit("Недостаточно данных. Возможно, обучение производилось по фотографии. Попробуйте "
                              "покрутить фотографию")
                print("Неточное обучение")
            self.data_set[self.name] = self.person_features
            f = open(self.jsonpath, 'w')
            f.write(json.dumps(self.data_set))
            self.log.emit("Завершение идентификации по просьбе пользователя")
            self.successfulSaveIdentificationResult.emit()
            self.quit()
        except Exception as e:
            print(str(e))

